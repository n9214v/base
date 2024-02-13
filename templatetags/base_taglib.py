#
#   All template tags provided by the MJG Base plugin are registered in this file.
#   For browse-ability, all processing happens outside this file.
#

from django.conf import settings
from django import template
from ..classes.log import Log
from ..models import Feature
from ..services import utility_service, auth_service, date_service, validation_service
from ..templatetags.tag_processing import supporting_functions as support, html_generating, static_content
from django.urls import reverse
from decimal import Decimal
from django.utils.html import mark_safe
from django.template import TemplateSyntaxError
import time

register = template.Library()
log = Log()


# # # # # # # # # # # # # # # # # # #
# UTILITY CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.filter
def get(p_dict, p_key):
    return p_dict.get(p_key) if p_dict else None


@register.filter
def collect(p_list, p_attr):
    """
    Given a list of objects, return a list of specific attribute values
    Example: collect(course_detail_list, "crn") -- would return a list of CRNs
    """
    return [xx.get(p_attr) if type(xx) is dict else getattr(xx, p_attr) for xx in p_list] if p_list else []


@register.filter
def maxlen(model_instance, field_name):
    """
    Given a model and field, return the max allowed length of that field
    """
    return validation_service.get_max_field_length(field_name, model_instance)


@register.simple_tag(takes_context=True)
def absolute_url(context, *args, **kwargs):
    if args:
        reverse_args = args[1:] if len(args) > 1 else None
        return f"{context['absolute_root_url']}{reverse(args[0], args=reverse_args)}"
    else:
        return context['absolute_root_url']


@register.simple_tag()
def flash_variable(*args, **kwargs):
    var = kwargs.get('var', args[0] if args else None)
    alt = kwargs.get('alt', args[1] if args and len(args) >= 2 else None)
    return utility_service.get_flash_scope(var, alt)


@register.simple_tag()
def app_code():
    return utility_service.get_app_code()


@register.simple_tag()
def app_name():
    return utility_service.get_setting('APP_NAME')


@register.simple_tag()
def app_version():
    return utility_service.get_app_version()


@register.simple_tag()
def setting_value(setting_name, default_value=None):
    return utility_service.get_setting(setting_name, default_value)


@register.filter
def get_setting(setting_name, default_value=None):
    """Get setting with default value. Usable in an IF or FOR tag"""
    return utility_service.get_setting(setting_name, default_value)


@register.simple_tag(takes_context=True)
def set_var(context, *args, **kwargs):
    context[args[0]] = args[1]
    return ''


@register.simple_tag(takes_context=True)
def decode(context, *args):
    """
    Given an ID, return it's label from a dict of options.
    Optional third argument is a default value

    Ex:  {% decode department_code department_options %}
         {% decode 'CS' department_options %}
         {% decode 'N$^&' department_options 'Invalid Department' %}
    """
    value = args[1].get(args[0])
    if value is None and len(args) == 3:
        return args[2]
    return value


@register.simple_tag
def format_phone(*args):
    # Phone could be in one arg, or split (area, phone, ext)
    return utility_service.format_phone(''.join([x for x in args if x]))


@register.simple_tag
def format_decimal(*args, **kwargs):
    amount = None
    try:
        amount = args[0]

        # Return empty-string for None values
        if amount is None:
            return ""

        # Convert to Decimal
        amount_str = str(amount).replace(",", "").replace("$", "")
        amount_decimal = Decimal(amount_str)

        # Allow some formatting options
        prefix = kwargs["prefix"] if "prefix" in kwargs and kwargs["prefix"] else ""
        use_commas = "comma" not in kwargs or bool(kwargs["comma"])
        show_decimals = "decimal" not in kwargs or bool(kwargs["decimal"])

        # Format the number as a string
        if use_commas and show_decimals:
            formatted_string = "{0:,.2f}".format(amount_decimal)
        elif use_commas:
            formatted_string = "{0:,.0f}".format(amount_decimal)
        elif show_decimals:
            formatted_string = "{0:.2f}".format(amount_decimal)
        else:
            formatted_string = "{0:.0f}".format(amount_decimal)

        return f"{prefix}{formatted_string}"

    except Exception as ee:
        log.warn(f"Error formatting '{amount}' as decimal. {ee}")
        return ""


@register.simple_tag
def format_currency(*args, **kwargs):
    kwargs.update({'prefix': '$'})
    return format_decimal(*args, **kwargs)


@register.simple_tag()
def format_date(datetime_instance):
    return date_service.to_date_string(datetime_instance)


@register.simple_tag()
def format_datetime(datetime_instance):
    return date_service.to_datetime_string(datetime_instance)


@register.simple_tag()
def format_timestamp(datetime_instance):
    return date_service.to_timestamp_string(datetime_instance)


@register.filter
def feature(feature_code, true_false):
    """
    Check if feature is enabled/disabled

    'my_feature'|feature:True   - Is feature enabled?
    'my_feature'|feature:False  - Is feature disabled?
    """
    is_enabled = Feature.is_enabled(feature_code)
    if true_false and is_enabled:
        return True
    elif (not true_false) and (not is_enabled):
        return True
    else:
        return False


# # # # # # # # # # # # # # # # # # #
# AUTHENTICATION CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.filter
def has_authority(authority_code, true_false):
    """
    Check if current user does/does not have permission

    'admin'|has_authority:True   - Does user have admin?
    'admin'|has_authority:False  - Does user not have admin?

    'admin,infotext'|has_authority:True - Can provide csv list of authorities
    """
    has_it = auth_service.has_authority(authority_code)
    if true_false and has_it:
        return True
    elif (not true_false) and (not has_it):
        return True
    else:
        return False


@register.simple_tag(takes_context=True)
def check_admin_menu(context, *args, **kwargs):
    # All power users see the admin menu
    admin_menu_roles = []

    # Other MJG plugins may include items for specific roles other than power-user roles
    for admin_link in context['plugin_admin_links']:
        if 'authorities' in admin_link:
            plus = utility_service.csv_to_list(admin_link['authorities'])
            admin_menu_roles.extend(plus if plus else [])

    has_it = auth_service.has_authority(admin_menu_roles)
    var_name = args[0] if len(args) > 0 else 'admin_menu'
    context[f"has_{var_name}"] = has_it
    context[f"does_not_have_{var_name}"] = not has_it
    return ''

# # # # # # # # # # # # # # # # # # #
# STATIC CONTENT CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.simple_tag
def static_content_url():
    return utility_service.get_static_content_url()


@register.simple_tag
def jquery(*args, **kwargs):
    return static_content.jquery(*args, **kwargs)


@register.simple_tag
def bootstrap(*args, **kwargs):
    return static_content.bootstrap(*args, **kwargs)


@register.simple_tag
def font_awesome(*args, **kwargs):
    return static_content.font_awesome(*args, **kwargs)


@register.simple_tag
def datatables(*args, **kwargs):
    return static_content.datatables(*args, **kwargs)


@register.simple_tag
def jquery_confirm(*args, **kwargs):
    return mark_safe(static_content.jquery_confirm(*args, **kwargs))


@register.simple_tag
def chosen(*args, **kwargs):
    return static_content.chosen(*args, **kwargs)


@register.simple_tag
def cdn_js(*args, **kwargs):
    return static_content.cdn_js(*args, **kwargs)


@register.simple_tag
def cdn_css(*args, **kwargs):
    return static_content.cdn_css(*args, **kwargs)


@register.tag()
def image(parser, token):
    return html_generating.ImageNode(token.split_contents())


# # # # # # # # # # # # # # # # # # #
# HTML-GENERATING CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.inclusion_tag('base/components/pagination.html')
def pagination(paginated_results):
    """Example: {%pagination polls%}"""
    return html_generating.pagination(paginated_results)


@register.tag()
def sortable_th(parser, token):
    """Sortable <th> that works with server-side pagination"""
    return html_generating.SortableThNode(token.split_contents())


@register.tag()
def fa(parser, token):
    """Render a screen-reader-friendly FontAwesome4 icon"""
    return html_generating.FaNode(token.split_contents())


@register.tag()
def select_menu(parser, token):
    return html_generating.SelectNode(token.split_contents())


@register.tag()
def js_alert(parser, token):
    """
    Simple jquery-confirm alert
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.JsAlert(nodelist, tokens)


@register.tag()
def js_confirm(parser, token):
    """
    Simple jquery-confirm confirmation box
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.JsConfirm(nodelist, tokens)


@register.tag()
def popup(parser, token):
    """
    Create a popup "window"
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.Popup(nodelist, tokens)


@register.tag()
def page_load_ind(parser, token):
    """
    Create a spinning icon over a non-dismiss-able smokescreen
    """
    return html_generating.PageLoadInd(token.split_contents())


@register.tag()
def header_nav_menu_item(parser, token):
    """Example:  """
    return html_generating.HeaderNavMenuItem(token.split_contents())


@register.tag()
def header_nav_tab(parser, token):
    """Example:  """
    return html_generating.HeaderNavTab(token.split_contents())


@register.simple_tag()
def posted_message_birth_date():
    return int(time.time())
