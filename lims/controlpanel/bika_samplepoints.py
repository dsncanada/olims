from dependencies.dependency import ClassSecurityInfo
from dependencies.dependency import schemata
from dependencies import atapi
from dependencies.dependency import registerType
from dependencies.dependency import permissions
from dependencies.dependency import getToolByName
from dependencies.dependency import safe_unicode
from lims.browser import BrowserView
from lims.browser.bika_listing import BikaListingView
from lims.config import PROJECTNAME
from dependencies.dependency import IViewView
from lims import bikaMessageFactory as _
from lims.utils import t
from dependencies.dependency import PloneMessageFactory as _p
from lims.interfaces import ISamplePoints
from lims.content.bikaschema import BikaFolderSchema
from dependencies.dependency import IFolderContentsView
from dependencies.folder import ATFolder, ATFolderSchema
from dependencies.dependency import implements
from dependencies.dependency import getToolByName
from dependencies.dependency import check as CheckAuthenticator
import json


class SamplePointsView(BikaListingView):
    implements(IFolderContentsView, IViewView)

    def __init__(self, context, request):
        super(SamplePointsView, self).__init__(context, request)
        self.catalog = 'bika_setup_catalog'
        self.contentFilter = {'portal_type': 'SamplePoint',
                              'sort_on': 'sortable_title'}
        self.context_actions = {_('Add'):
                                {'url': 'createObject?type_name=SamplePoint',
                                 'icon': '++resource++bika.lims.images/add.png'}}
        self.title = self.context.translate(_("Sample Points"))
        self.icon = self.portal_url + "/++resource++bika.lims.images/samplepoint_big.png"
        self.description = ""
        self.show_sort_column = False
        self.show_select_row = False
        self.show_select_column = True
        self.pagesize = 25

        self.columns = {
            'Title': {'title': _('Sample Point'),
                      'index':'sortable_title'},
            'Description': {'title': _('Description'),
                            'index': 'description',
                            'toggle': True},
            'Owner': {'title': _p('Owner'),
                      'toggle': True},
            'getComposite': {'title': _('Composite'),
                             'toggle': True},
            'SampleTypes': {'title': _('Sample Types'),
                            'toggle': True},
        }

        self.review_states = [
            {'id':'default',
             'title': _('Active'),
             'contentFilter': {'inactive_state': 'active'},
             'transitions': [{'id':'deactivate'}, ],
             'columns': ['Title', 'Description', 'Owner', 'SampleTypes']},
            {'id':'inactive',
             'title': _('Dormant'),
             'contentFilter': {'inactive_state': 'inactive'},
             'transitions': [{'id':'activate'}, ],
             'columns': ['Title', 'Description', 'Owner', 'SampleTypes']},
            {'id':'all',
             'title': _('All'),
             'contentFilter':{},
             'columns': ['Title', 'Description', 'Owner', 'SampleTypes']},
        ]

    def folderitems(self):
        items = BikaListingView.folderitems(self)
        for x in range(len(items)):
            if not items[x].has_key('obj'): continue
            obj = items[x]['obj']
            items[x]['replace']['Title'] = "<a href='%s'>%s</a>" % \
                 (items[x]['url'], items[x]['Title'])
            items[x]['Description'] = obj.Description()
            titles = [st.Title() for st in obj.getSampleTypes()]
            items[x]['SampleTypes'] = ",".join(titles)
            if obj.aq_parent.portal_type == 'Client':
                items[x]['Owner'] = obj.aq_parent.Title()
            else:
                items[x]['Owner'] = self.context.bika_setup.laboratory.Title()
        return items

schema = ATFolderSchema.copy()

class SamplePoints(ATFolder):
    implements(ISamplePoints)
    displayContentsTab = False
    schema = schema

schemata.finalizeATCTSchema(schema, folderish = True, moveDiscussion = False)
atapi.registerType(SamplePoints, PROJECTNAME)

class ajax_SamplePoints(BrowserView):
    """ The autocomplete data source for sample point selection widgets.
        Returns a JSON list of sample point titles.

        Request parameters:

        - sampletype: if specified, it's expected to be the title
          of a SamplePoint object.  Optionally, the string 'Lab: ' might be
          prepended, to distinguish between Lab and Client objects.

        - term: the string which will be searched against all SamplePoint
          titles.

        - _authenticator: The plone.protect authenticator.

    """

    def filter_list(self, items, searchterm):
        if searchterm and len(searchterm) < 3:
            # Items that start with A or AA
            res = [s.getObject()
                     for s in items
                     if s.title.lower().startswith(searchterm)]
            if not res:
                # or, items that contain A or AA
                res = [s.getObject()
                         for s in items
                         if s.title.lower().find(searchterm) > -1]
        else:
            # or, items that contain searchterm.
            res = [s.getObject()
                     for s in items
                     if s.title.lower().find(searchterm) > -1]
        return res

    def __call__(self):
        CheckAuthenticator(self.request)
        bsc = getToolByName(self.context, 'bika_setup_catalog')
        term = safe_unicode(self.request.get('term', '')).lower()
        items = []
        if not term:
            return json.dumps(items)
        # Strip "Lab: " from sample point title
        term = term.replace("%s: " % _("Lab"), '')
        sampletype = safe_unicode(self.request.get('sampletype', ''))
        if sampletype and len(sampletype) > 1:
            st = bsc(portal_type = "SampleType",
                     title = sampletype,
                     inactive_state = 'active')
            if not st:
                return json.dumps([])
            st = st[0].getObject()
            items = [o.Title() for o in st.getSamplePoints()]

        if not items:
            client_items = lab_items = []

            # User (client) sample points
            if self.context.portal_type in ('Client', 'AnalysisRequest'):
                if self.context.portal_type == 'Client':
                    client_path = self.context.getPhysicalPath()
                else:
                    client_path = self.context.aq_parent.getPhysicalPath()
                client_items = list(
                    bsc(portal_type = "SamplePoint",
                        path = {"query": "/".join(client_path), "level" : 0 },
                        inactive_state = 'active',
                        sort_on='sortable_title'))

            # Global (lab) sample points
            lab_path = self.context.bika_setup.bika_samplepoints.getPhysicalPath()
            lab_items = list(
                bsc(portal_type = "SamplePoint",
                    path = {"query": "/".join(lab_path), "level" : 0 },
                    inactive_state = 'active',
                    sort_on='sortable_title'))

            client_items = [callable(s.Title) and s.Title() or s.title
                     for s in self.filter_list(client_items, term)]
            lab_items = [callable(s.Title) and s.Title() or s.title
                     for s in self.filter_list(lab_items, term)]
            lab_items = ["%s: %s" % (_("Lab"), safe_unicode(i))
                         for i in lab_items]

            items = client_items + lab_items

        return json.dumps(items)
