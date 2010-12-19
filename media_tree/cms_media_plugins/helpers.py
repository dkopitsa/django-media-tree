from django.core.urlresolvers import reverse

class PluginLink(object):
    
    LINK_PAGE = 'P'
    LINK_URL = 'U'
    LINK_IMAGE_DETAIL = 'I'
    LINK_URL_REVERSE = 'R'
    
    def __init__(self, type, url=None, obj=None, rel=None, target=None, querystring=''):
        self.type = type
        self.url = url
        self.obj = obj
        self.target = target
        self.querystring = querystring
        if self.type == PluginLink.LINK_IMAGE_DETAIL:
            self.url = ['media_tree_image_detail', self.obj.pk]
            self.rel = 'image-detail'

    def href(self):
        href = None
        if self.type == PluginLink.LINK_URL:
            href = self.url
        if self.type in (PluginLink.LINK_URL_REVERSE, PluginLink.LINK_IMAGE_DETAIL):
            if isinstance(self.url, basestring):
                parts = self.url.split(' ')
            else:
                parts = self.url
            name = parts.pop(0)
            try:
                href = reverse(name, args=parts)
            except NoReverseMatch:
                return False
        if self.type == PluginLink.LINK_PAGE:
            href = self.obj.get_absolute_url()
        if href != None:
            href += self.querystring
        return href

    @staticmethod
    def create_from(instance):
        if not getattr(instance, 'link_type', None):
            return None
        querystring = ''
        if instance.link_type == PluginLink.LINK_PAGE:
            link_obj = instance.link_page
        elif instance.link_type == PluginLink.LINK_IMAGE_DETAIL:
            link_obj = instance.node
            if getattr(instance, 'page', None):
                querystring = '?back_page='+str(instance.page.pk)
        else:
            link_obj = None
        return PluginLink(instance.link_type, url=instance.link_url, obj=link_obj, target=instance.link_target, querystring=querystring)


class FolderLinkBase(object):
    plugin_instance = None
    filter_media_types = None
    current_folder = None

    def __init__(self, node, count_descendants=True):
        self.node = node
        self.count_descendants = count_descendants

    @staticmethod
    def folder_param_name(plugin_instance):
        return 'folder-%i' % plugin_instance.pk

    def get_link_content(self):
        return self.node.__unicode__()

    def __unicode__(self):
        if self.count_descendants:
            descendants = self.node.get_descendants()
            if self.filter_media_types:
                descendants = descendants.filter(media_type__in=self.filter_media_types)
            count = ' <span class="count">(%i)</span>' % descendants.count()
        else:
            count = ''

        if issubclass(self.node.__class__, dict):
            name = self.node['name']
            pk = self.node['pk']
        else:
            name = self.get_link_content()
            pk = self.node.pk
        if pk:
            query = '%s=%i' % (self.__class__.folder_param_name(self.plugin_instance), pk)
        else:
            query = ''

        a_attrs = ''
        if self.node == self.current_folder:
            a_attrs += ' class="selected"'

        return mark_safe(u'<a%s href="?%s">%s</a>%s' % 
            (a_attrs, query, name, count))
