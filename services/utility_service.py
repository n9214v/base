from django.conf import settings
from django.db.models import Q
from ..classes.log import Log
from crequest.middleware import CrequestMiddleware
from inspect import getframeinfo, stack, getmembers
from collections import OrderedDict
import re
import os
import hashlib
import requests
import base64
import sys
from io import StringIO
from html.parser import HTMLParser

log = Log()
unit_test_session = {'modified': False, 'warned': False}
session_prefix = 'demo~'


def get_setting(property_name, default_value=None):
    """
    Get the value of a setting from settings or local_settings
    """
    return getattr(settings, property_name) if hasattr(settings, property_name) else default_value


def get_app_code():
    """
    Get the code that uniquely identifies this site
    """
    return get_setting('APP_CODE')


def get_app_name():
    """
    Get the human-readable name of the current application
    This is mainly used in administrative views
    """
    return get_setting("APP_NAME")


def get_app_version():
    """
    Get the version of the current application or sub-application
    """
    # Try to get from current app's (or sub-app's) __init__ version
    current_app_code = get_app_code().lower()
    try:
        for stuff in getmembers(sys.modules[current_app_code]):
            if "__version__" in stuff:
                return stuff[1]
    except Exception as ee:
        log.debug(f"Cannot determine version of {current_app_code}")

    # Return version from settings if not found in __init__
    return get_setting("APP_VERSION")


def get_installed_plugins():
    """
    Get a dict of the installed MJG plugins and their versions
    """
    installed_apps = {}
    for app_name in get_setting('INSTALLED_APPS'):
        version = "?"
        try:
            for stuff in getmembers(sys.modules[f'{app_name}']):
                if '__version__' in stuff:
                    version = stuff[1]
        except Exception as ee:
            log.debug(f"Cannot determine version of {app_name}")
        installed_apps[app_name] = version

    return installed_apps


def get_environment():
    """
    Get environment: DEV, STAGE, PROD
    """
    env = settings.ENVIRONMENT.upper()
    if env in ['DEV', 'STAGE', 'PROD']:
        return env
    else:
        return 'DEV'


def is_production():
    return get_environment() == 'PROD'


def is_non_production():
    return get_environment() != 'PROD'


def is_development():
    return (get_environment() == 'DEV') and settings.DEBUG


def get_static_content_url():
    if is_production():
        return 'https://sunny-kulfi-ca2031.netlify.app/cdn'
        # return 'https://d3hj6oqj41ttxz.cloudfront.net'
    else:
        # ToDo: Stage CDN
        return 'https://sunny-kulfi-ca2031.netlify.app/cdn'


def is_health_check():
    request = get_request()
    return request and 'HTTP_USER_AGENT' in request.META and 'HealthChecker' in request.META['HTTP_USER_AGENT']


def get_request():
    return CrequestMiddleware.get_request()


def get_parameters():
    """Get parameters as dict. This is mostly for logging parameters."""
    request = get_request()
    if request:
        pp = request.GET.items() if request.method == 'GET' else request.POST.items()
        return {kk: vv for kk, vv in pp}
    return None


def get_browser():
    try:
        request = get_request()
        browser = request.META["HTTP_USER_AGENT"]
    except:
        browser = "Unknown"
    return browser


def is_ajax():
    # request.is_ajax was deprecated in Django 3.1 and no longer exists in 3.2.10
    return get_request().headers.get('x-requested-with') == 'XMLHttpRequest'


def pagination_sort_info(
        request, default_sort="id", default_order="asc", filter_name=None, reset_page=False, sort_tuple=True
):
    """
    Get the pagination sort order and page info.
    Sort info, page number, and filters are automatically tracked in the session.

    Parameters:
        request:        Django 'request' object (from view)
        default_sort:   Property/Column to sort by
        default_order:  asc or desc
        filter_name:    If view is filtering on a keyword string, or list of keyword strings, maintain that here as well
        reset_page:     True will force back to page 1 (i.e. new search/filter terms submitted)
        sort_tuple:     Return tuple rather than string as sort parameter. Allows multiple sort columns.
    Returns tuple: (sortby-string-or-tuple, page-number)
        sortby-string includes column and direction ('id', '-id')
        page-number is recommended page number (reset to 1 after sort change)

        if filter_name was given, tuple will have a third item:
            - if filter_name is a single item: a single string will be returned
            - if filter_name is a list of names, a dict of {name: value} will be returned
    """

    # Make sure filter name is a list (with 0, 1, or more items)
    if not filter_name:
        filter_name_list = []
    elif type(filter_name) is list:
        filter_name_list = filter_name
    else:
        filter_name_list = [filter_name]

    fn = _get_cache_key()
    sort_var = f"{fn}-sort"
    order_var = f"{fn}-order"
    page_var = f"{fn}-page"
    filter_vars = {}
    for ff in filter_name_list:
        filter_vars[ff] = f"{fn}-filter-{ff}"

    # Get default sort, order, filter, page
    default_sort = get_session_var(sort_var, default_sort)
    default_order = get_session_var(order_var, default_order)
    default_page = get_session_var(page_var, 1)

    default_filters = {}
    for ff in filter_name_list:
        default_filters[ff] = get_session_var(filter_vars[ff], None)

    # Make default sort a tuple
    if type(default_sort) in [tuple, list]:
        default_sort = tuple(default_sort)
    elif default_sort:
        default_sort = (default_sort, )

    # Get values from parameters
    specified_sort = request.GET.get('sort', None)
    if specified_sort and ',' in specified_sort:
        specified_sort = csv_to_list(specified_sort)
    specified_order = request.GET.get('order', None)
    page = request.GET.get('page', default_page)

    specified_filters = {}
    for ff in filter_name_list:
        if ff in request.GET:
            # Get parameter as a list
            as_list = request.GET.getlist(ff, None)

            # If filter is named with "list" then treat it as a list even if it has 0 or 1 value
            if 'list' in ff:
                specified_filters[ff] = as_list
            # If not named as a list, but multiple values are present, return as a list
            elif as_list and len(as_list) > 1:
                specified_filters[ff] = as_list
            # Otherwise, return single value
            else:
                specified_filters[ff] = request.GET.get(ff, None)

        else:
            specified_filters[ff] = default_filters.get(ff)

    # Did the sort column change?
    if not specified_sort:
        sort_changed = False
    elif type(specified_sort) is list:
        sort_changed = specified_sort[0] and specified_sort[0] != default_sort[0]
        if len(specified_sort) > 1 and not sort_changed:
            if len(default_sort) < 2:
                sort_changed = True
            else:
                sort_changed = specified_sort[1] and specified_sort[1] != default_sort[1]
    else:
        sort_changed = specified_sort and specified_sort != default_sort[0]

    filter_changed = False
    for ff in filter_name_list:
        if ff in request.GET and specified_filters[ff] != default_filters[ff]:
            filter_changed = True

    # If sort is specified, adjust order as needed and return to page 1
    if specified_sort:
        page = 1

        # If sort has changed
        if sort_changed:
            # default to ascending order
            order = 'asc'

            # make secondary sort by the previous selection
            try:
                if type(specified_sort) is list:
                    sort = tuple(specified_sort)
                else:
                    sort = (specified_sort, )

                if default_sort:
                    sort = sort + (default_sort[0], )

            except Exception as ee:
                log.error(f"Error updating default sort ({default_sort}): {ee}")
                sort = (specified_sort, )

        # If sort has not changed
        elif specified_order:
            sort = default_sort
            order = specified_order

        # If sort stayed the same toggle between asc and desc
        else:
            sort = default_sort
            order = 'asc' if default_order == 'desc' else 'desc'

    # If sort not specified, use default
    else:
        sort = default_sort
        order = default_order

    # If filter string changed, page will need to be reset
    if filter_changed:
        filter_strings = specified_filters
        page = 1
    else:
        filter_strings = default_filters

    if reset_page:
        page = 1

    # Remember sort preference
    set_session_var(sort_var, sort)
    set_session_var(order_var, order)
    set_session_var(page_var, page)
    for ff in filter_name_list:
        set_session_var(filter_vars[ff], filter_strings[ff])

    # Sortable column header taglib needs to know the last-sorted column
    # This assumes only one sorted dataset is being displayed at a time
    set_session_var('psu_last_secondary_sorted_column', sort[1] if type(sort) is tuple and len(sort) > 1 else sort)
    set_session_var('psu_last_sorted_column', sort[0] if type(sort) is tuple else sort)
    set_session_var('psu_last_sorted_direction', order)

    oo = '-' if order == 'desc' else ''
    if type(sort) is tuple:
        sort_param = ()
        for vv in sort:
            sort_param += (f"{oo}{vv}", )

    elif sort:
        sort_param = (f"{oo}{sort}", )

    else:
        sort_param = None

    # If tuple not being used for sort param
    if not sort_tuple:
        sort_param = sort_param[0] if sort_param else None

    if filter_name:
        if len(filter_strings) == 1:
            return_val = sort_param, page, filter_strings[filter_name]
        else:
            return_val = sort_param, page, filter_strings
    else:
        return_val = sort_param, page

    return return_val


def get_session():
    # While unit testing, there will be no request
    request = get_request()

    if request is None:
        # This should not happen in prod, but just to be sure
        if is_production():
            log.error("Request does not exist. Could not retrieve session.")
            return None
        else:
            # Only warn about this once (to prevent cluttered logs)
            if not unit_test_session.get('warned'):
                log.warning("No request. Using dict as session (assumed unit testing)")
                unit_test_session['warned'] = True
            return unit_test_session
    else:
        return request.session


def set_session_var(var, val):
    # Prefix all custom session entries
    var = f"{session_prefix}{var}"
    session = get_session()
    session[var] = val
    return val


def get_session_var(var, alt=None):
    # Prefix all custom session entries
    var = f"{session_prefix}{var}"
    session = get_session()
    return session.get(var, alt)


def clear_custom_session_vars(preserve=None):
    request = get_request()
    if preserve and type(preserve) is not list:
        preserve = [preserve]
    keep = [f"{session_prefix}{kk}" for kk in preserve] if preserve else None
    for kk in list(request.session.keys()):
        if kk.startswith(session_prefix):
            if keep and kk in keep:
                continue
            else:
                del request.session[kk]
    request.session.modified = True


def set_page_scope(var, val):
    var_name = f"page_scope_{var}"
    set_session_var(var_name, val)
    return val


def get_page_scope(var, alt=None):
    var_name = f"page_scope_{var}"
    return get_session_var(var_name, alt)


def set_flash_scope(var, val):
    var_name = f"flash_scope_{var}"
    set_session_var(var_name, val)
    return val


def get_flash_scope(var, alt=None):
    # Get the value saved in previous request
    prev_var_name = f"flashed_scope_{var}"
    previous_flash_value = get_session_var(prev_var_name, alt)

    # Get new value if overwritten during the current request
    new_var_name = f"flash_scope_{var}"
    new_flash_value = get_session_var(new_var_name, 'flash-variable-not-set')

    # return the more recent of the two
    # (flash variable from last request can be overwritten this request)
    if new_flash_value != 'flash-variable-not-set':
        return new_flash_value
    else:
        return previous_flash_value


def cycle_flash_scope():
    session = get_session()
    flash_vars = []
    flashed_vars = []
    for kk in session.keys():
        if kk.startswith(f'{session_prefix}flash_scope_'):
            flash_vars.append(kk)
        elif kk.startswith(f'{session_prefix}flashed_scope_'):
            flashed_vars.append(kk)
    # Remove the keys from the flashed scope
    for kk in flashed_vars:
        del session[kk]
    # Move flash vars to flashed scope
    for kk in flash_vars:
        new_kk = kk.replace('flash_', 'flashed_')
        session[new_kk] = session[kk]
        del session[kk]

    session['modified'] = True


def clear_breadcrumbs():
    set_session_var("base_breadcrumbs", [])
    set_page_scope("base_breadcrumbs_inti", True)


def add_breadcrumb(
        label,
        url=None,
        icon=None, icon_only=False,
        active=False,
        reset=False,
        duplicate=False,
):
    bcs = get_breadcrumbs()
    if reset or not bcs:
        bcs = []

        # Reset breadcrumb list (optionally start with Home link)
        if reset and "home" in str(reset).lower():
            home = {
                "label": "Home",
                "url": "/",
            }
            if "icon" in str(reset).lower(): # and
                home["icon"] = "fa-home"
                if "only" in str(reset).lower():
                    home["icon_only"] = True
            bcs.append(home)

    if bcs and not duplicate:
        # If this label already exists, it will be removed
        # The new breadcrumb will be added to the end
        bcs = [x for x in bcs if x.get("label") != label]

    bcs.append({
        "label": label,
        "url": url,
        "active": active,
        "icon": icon,
        "icon_only": icon_only,
    })
    return set_session_var("base_breadcrumbs", bcs)


def get_breadcrumbs():
    init_ind = bool(get_page_scope("base_breadcrumbs_inti"))
    bcs = get_session_var("base_breadcrumbs", [])
    if not init_ind:
        ii = 0
        of = len(bcs)
        for bc in bcs:
            ii += 1
            bc["reload_ind"] = f"{ii}/{of}"
    return get_session_var("base_breadcrumbs", [])


def store(value):
    """
    Store the result of a function for the duration of the request.
    Note: If the stored response is mutable, changes made to the returned value will affect the cached instance as well
    """
    set_page_scope(_get_cache_key(), value)
    return value


def recall(alt=None):
    """
    Retrieve a stored result from a function run earlier in the request
    Note: If the stored response is mutable, changes made to the returned value will affect the cached instance as well
    """
    value = get_page_scope(_get_cache_key())
    if value is None:
        return alt
    return value


def _get_cache_key():
    """
    Private function
    Get the key used by store/recall functions above
    UPDATE: This is also used for remembering pagination sort/order
    """
    # Ignore this function, and the store/recall function that called it
    depth = 2

    # Get the info about the function that called the store/recall function
    caller = getframeinfo(stack()[depth][0])

    # Use filename without .py extension
    filename = os.path.basename(caller.filename)[:-3]

    return f"cache-{filename}-{caller.function}"


def test_cache_key():
    """
    The only purpose of this function is to unit test the "cache key" generated above
    """
    return _get_cache_key()


def test_store_recall(value=None):
    """
    The only purpose of this function is to unit test the store/recall feature
    """
    if value:
        store(value)
    else:
        return recall()


def clear_page_scope():
    log.trace()
    session = get_session()
    temp_vars = []
    for kk in session.keys():
        if kk.startswith(f'{session_prefix}page_scope_'):
            temp_vars.append(kk)
    # Remove the keys from the session
    for kk in temp_vars:
        del session[kk]

    session['modified'] = True


def csv_to_list(src, convert_int=False):
    """Turn a string of comma-separated values into a python list"""
    result_list = None

    # If a list was already given, no conversion needed
    if type(src) is list or type(src) is None:
        result_list = src

    else:
        # Make sure we're working with a string
        src = str(src)

        # If the string "None" was given, return None
        if src == 'None':
            return None

        # Often, this is a python list that has been converted to a string at some point
        if src[0] == '[' and src[-1] == ']':
            src = src[1:-1]  # Remove brackets

        result_list = [ii.strip('"\' ') if type(ii) is str else ii for ii in src.split(',') if ii]

    # If converting list elements to a specified type
    if convert_int:
        return [int(ii) if type(ii) is str else ii for ii in result_list]
    # elif convert_<future-type>:
    #    return ...
    else:
        return result_list


def options_list_to_dict(options):
    """
    Finti returns options from validation tables as a list of dicts.
    This function converts the list of dicts to a single dict of options
    """
    # Expecting a list of {id:, value:} dicts
    # A list of {key:, value:} dicts will also work
    if type(options) is list:
        # Convert the list to one big dict
        option_dict = OrderedDict()
        for ii in options:
            option_dict[ii['id' if 'id' in ii else 'key']] = ii['value']
        return option_dict
    elif type(options) is dict:
        return options
    else:
        log.error(
            "Invalid datatype for options. Expecting list of {0}. Got {1}".format('{id:, value:} dicts', type(options))
        )


def get_gravatar_image_src(email_address):
    """
        If the user has a Gravatar image, it will be used as their default profile image.
    """
    if get_setting('DISABLE_GRAVATAR'):
        return None

    if not email_address:
        return None

    log.trace([email_address])
    try:
        email = email_address.strip().lower()
        m = hashlib.md5()
        m.update(email.encode())
        email_hash = m.hexdigest()

        # ToDo: Provide an alt image so that a consistent response can indicate not having a Gravatar image
        alt_img = f"/images/no-id-photo.png"
        url = f"https://www.gravatar.com/avatar/{email_hash}?s=200&d={alt_img}"

        # Get the image data
        b64img = base64.b64encode(requests.get(url).content).decode()

        # If this is the default image, return None
        if b64img.startswith('iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAMAAABrrFhUAAAAM1BMVEXn6+7g5em4xMvFz9XM1drk6Oy/ydCxvsa0wcn'):
            return None

        return """data:image/jpg;base64,{0}""".format(b64img)

    except Exception as ee:
        log.error(f"Error getting Gravatar image: {str(ee)}")
        return None


def format_phone(phone_number, no_special_chars=False):
    """
    Format a phone number.
    """
    src = initial_string = str(phone_number) if phone_number else ''
    if ' ext ' in initial_string:
        src = initial_string.replace(' ext ', '')
    word_chars_only = re.sub(r'\W', "", src).upper()
    digits_only = re.sub(r'\D', "", src)

    # Remove unnecessary country code
    if len(digits_only) == 11 and digits_only.startswith('1'):
        digits_only = digits_only[1:]

    # Maybe it's an abbreviated campus number
    elif len(digits_only) == 5 and digits_only.startswith('5'):
        digits_only = "50372{}".format(digits_only)
    elif len(digits_only) == 7 and digits_only.startswith('725'):
        digits_only = "503{}".format(digits_only)

    # If a clean 10-digit number was given, split into the standard pieces
    # If longer than 10 digits, assume extra to be an extension
    if len(digits_only) > 10:
        if no_special_chars:
            return digits_only
        else:
            return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:10]} ext {digits_only[10:]}"
    elif len(digits_only) == 10:
        if no_special_chars:
            return digits_only
        else:
            return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:10]}"

    # If too short, just return it as-is. Maybe a real live human will figure it out.
    else:
        # If only 7-digits, return as a phone number with no area code
        if no_special_chars:
            return word_chars_only
        elif len(word_chars_only) == 7:
            return f"{word_chars_only[:3]}-{word_chars_only[3:]}"
        else:
            return initial_string.upper()


def decamelize(string):
    """Convert CamelCaseWord to camel_case_word"""
    result = ""
    ii = 0
    for xx in string:
        # if this is an upper case letter, add an underscore
        if xx != xx.lower() and ii != 0:
            result += '_'

        result += xx.lower()
        ii += 1

    return result


def camelize(string, cap_first_letter=True):
    """Convert camel_case_word to CamelCaseWord"""
    result = ""
    ii = 0
    cap_next_letter = cap_first_letter
    for xx in string:

        # if this is an underscore, capitalize next letter
        if xx == '_':
            cap_next_letter = True
            continue

        if cap_next_letter:
            result += xx.upper()
        else:
            result += xx.lower()

        cap_next_letter = False
        ii += 1

    return result


def strip_tags(html_string):
    # replace br with \n
    for br in ["<br>", "<br />", '<br style="clear:both;" />']:
        if f"{br}\n" in html_string:
            html_string = html_string.replace(f"{br}\n", "\n")
        if br in html_string:
            html_string = html_string.replace(br, "\n")
    if "\r" in html_string:
        html_string = html_string.replace("\r", "")
    s = MLStripper()
    s.feed(html_string)
    return s.get_data()


class MLStripper(HTMLParser):
    def error(self, message):
        pass

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()
