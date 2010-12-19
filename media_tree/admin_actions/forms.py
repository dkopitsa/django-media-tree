from media_tree.models import FileNode
from media_tree.fields import FileNodeChoiceField
from media_tree.forms import MetadataForm
from django import forms
from django.utils.translation import ugettext as _
from django.contrib.admin import helpers

class FileNodeActionsForm(forms.Form):

    enable_target_node_field = False
    success_count = 0
    confirm_fields = False

    def __init__(self, queryset, *args, **kwargs):
        super(FileNodeActionsForm, self).__init__(*args, **kwargs)
        valid_targets = FileNode._tree_manager.filter(node_type=FileNode.FOLDER)
        self.selected_nodes = queryset
        
        selected_nodes_pk = []
        if queryset:
            for node in queryset:
                opts = node._meta
                selected_nodes_pk.append(node.pk)
                valid_targets = valid_targets.exclude(**{
                    opts.tree_id_attr: getattr(node, opts.tree_id_attr),
                    '%s__gte' % opts.left_attr: getattr(node, opts.left_attr),
                    '%s__lte' % opts.right_attr: getattr(node, opts.right_attr),
                })
            self.fields[helpers.ACTION_CHECKBOX_NAME] = forms.ModelMultipleChoiceField(queryset=FileNode.objects.all(), initial=selected_nodes_pk, required=True, widget=forms.widgets.MultipleHiddenInput())

        self.fields['action'] = forms.CharField(initial=self.action_name, required=True, widget=forms.widgets.HiddenInput())
        if self.enable_target_node_field:
            self.fields['target_node'] = FileNodeChoiceField(label=_('to'), queryset=valid_targets, required=False)
        self.fields['execute'] = forms.BooleanField(initial=True, required=True, widget=forms.widgets.HiddenInput())

    def get_selected_nodes(self):
        if hasattr(self, 'cleaned_data') and helpers.ACTION_CHECKBOX_NAME in self.cleaned_data:
            return self.cleaned_data[helpers.ACTION_CHECKBOX_NAME]
        else:
            return self.selected_nodes

    def clean(self):
        if self.confirm_fields:
            self.confirmed_data = {}
            for key in self.cleaned_data.keys():
                if self.data.get('_confirm_'+key, False):
                    self.confirmed_data[key] = self.cleaned_data[key]
        return self.cleaned_data

class MoveSelectedForm(FileNodeActionsForm):

    action_name = 'move_selected'
    enable_target_node_field = True

    def move_node(self, node, target):
        try:
            # Reload object because tree attributes may be out of date 
            node = node.__class__.objects.get(pk=node.pk)
            descendant_count = node.get_descendants().count()
            node.move_to(target)
            self.success_count += 1 + descendant_count
            return node
        except InvalidMove, e:
            self.errors[NON_FIELD_ERRORS] = ErrorList(e)
            raise

    def save(self):
        """
        Attempts to move the nodes using the selected target and
        position.

        If an invalid move is attempted, the related error message will
        be added to the form's non-field errors and the error will be
        re-raised. Callers should attempt to catch ``InvalidMove`` to
        redisplay the form with the error, should it occur.
        """
        self.success_count = 0
        for node in self.get_selected_nodes():
            self.move_node(node, self.cleaned_data['target_node'])


class CopySelectedForm(FileNodeActionsForm):

    action_name = 'copy_selected'
    enable_target_node_field = True

    def copy_node(self, node, target):
        from django.core.files.uploadedfile import UploadedFile
        def clone_object(from_object):
            args = dict([(fld.name, getattr(from_object, fld.name))
                for fld in from_object._meta.fields
                    if fld is not from_object._meta.pk]);
            return from_object.__class__(**args)

        new_node = clone_object(node)
        # Creating an UploadedFile from the original file results in the file being copied on disk on save()
        new_node.file = UploadedFile(node.file, node.file.name, None, node.size)
        new_node.insert_at(target, commit=True)
        if new_node.node_type == FileNode.FOLDER:
            self.copy_nodes_rec(node.get_children(), new_node)
        return new_node

    def copy_nodes_rec(self, nodes, target):
        for node in nodes:
            self.copy_node(node, target)
            self.success_count += 1

    def save(self):
        self.success_count = 0
        self.copy_nodes_rec(self.get_selected_nodes(), self.cleaned_data['target_node'])


class ChangeMetadataForSelectedForm(FileNodeActionsForm):

    action_name = 'change_metadata_for_selected'
    enable_target_node_field = False
    confirm_fields = True

    def __init__(self, *args, **kwargs):
        super(ChangeMetadataForSelectedForm, self).__init__(*args, **kwargs)
        copy_form = MetadataForm()
        copy_fields = copy_form.fields
        exclude = ()
        for key in copy_fields.keys():
            if not key in self.fields and not key in exclude:
                self.fields[key] = copy_fields[key]
                model_field = copy_form.instance._meta.get_field(key)
                if model_field.validators:
                    for validator in model_field.validators:
                        if not validator in self.fields[key].validators:
                            self.fields[key].validators.append(validator)

    def update_node(self, node, metadata):
        changed = False
        for key in metadata:
            if getattr(node, key) != metadata[key]:
                setattr(node, key, metadata[key])
                changed = True
        node.save()
        return changed

    def save_nodes_rec(self, nodes):
        for node in nodes:
            if self.update_node(node, self.confirmed_data):
                self.success_count += 1
            if node.node_type == FileNode.FOLDER:
                self.save_nodes_rec(node.get_children())

    def save(self):
        self.success_count = 0
        self.save_nodes_rec(self.get_selected_nodes())
