from django import template

register = template.Library()

@register.filter(name='addclass')
def addclass(field, css):
    return field.as_widget(attrs={"class": css})

@register.filter(name='add_form_control')
def add_form_control(field):
    """Add form control classes to input fields"""
    css_classes = "block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
    
    # Check field type to apply appropriate classes
    if hasattr(field.field.widget, 'input_type'):
        if field.field.widget.input_type in ['datetime-local', 'date', 'time']:
            css_classes += " text-sm"
    
    if field.field.widget.__class__.__name__ == 'Textarea':
        css_classes = "block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white resize-none"
    
    if field.field.widget.__class__.__name__ == 'Select':
        css_classes = "block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
    
    return field.as_widget(attrs={"class": css_classes})

@register.filter(name='add_checkbox_class')
def add_checkbox_class(field):
    """Add checkbox classes"""
    css_classes = "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700"
    return field.as_widget(attrs={"class": css_classes}) 