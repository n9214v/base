from django import template
from django.utils.html import format_html
from ...services import utility_service
from ...classes.log import Log

log = Log()


def image_url():
    return f"{utility_service.get_static_content_url()}/images"


def lib_url():
    return f"{utility_service.get_static_content_url()}/lib"


def mjg_url(version='v1'):
    return f"{utility_service.get_static_content_url()}/{version}"


def jquery(*args, **kwargs):
    return format_html(f"""
    <script
      src="https://code.jquery.com/jquery-3.6.4.min.js"
      integrity="sha256-oP6HI9z1XaZNBrJURtCoUT5SUnxFr8s3BzRl+cbzUq8="
      crossorigin="anonymous"></script>
    """)


def bootstrap(*args, **kwargs):
    css = f"https://stackpath.bootstrapcdn.com/bootstrap/{kwargs.get('version', '5.3.0')}/css/bootstrap.min.css"
    js = f"https://stackpath.bootstrapcdn.com/bootstrap/{kwargs.get('version', '5.3.0')}/js/bootstrap.min.js"
    return format_html(
        f"""
        <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/2.9.2/umd/popper.min.js" integrity="sha512-2rNj2KJ+D8s1ceNasTIex6z4HWyOnEYLVC3FigGOmyQCZc2eBXKgOxQmo3oKLHyfcj53uz4QMsRCWNbLd32Q1g==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" integrity="sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN" crossorigin="anonymous">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.min.js" integrity="sha384-BBtl+eGJRgqQAUMxJ7pMwbEyER4l1g+O15P+16Ep7Q9Q+zqX6gSbd85u4mG4QzX+" crossorigin="anonymous"></script>
        """
    )


def datatables(*args, **kwargs):
    return format_html(
        f"""
        <link rel="stylesheet" href="https://cdn.datatables.net/{kwargs.get('version', '1.10.22')}/css/jquery.dataTables.min.css" />
        <script src="https://cdn.datatables.net/{kwargs.get('version', '1.10.22')}/js/jquery.dataTables.min.js"></script>
        """
    )


def jquery_confirm(*args, **kwargs):
    defaults = """
        <script type="text/javascript">
            jconfirm.defaults = {
                title: false,
                content: 'Are you sure?',
                contentLoaded: function(){},
                icon: '',
                confirmButton: 'Okay',
                cancelButton: 'Cancel',
                confirmButtonClass: 'btn-default',
                cancelButtonClass: 'btn-default',
                theme: 'modern',
                animation: 'Rotate',
                closeAnimation: 'scale',
                animationSpeed: 500,
                animationBounce: 1.2,
                keyboardEnabled: true,
                rtl: false,
                confirmKeys: [13], // ENTER key
                cancelKeys: [27], // ESC key
                container: 'body',
                confirm: function () {},
                cancel: function () {},
                backgroundDismiss: false,
                autoClose: false,
                closeIcon: null,
                columnClass: 'col-md-4 col-md-offset-4 col-sm-6 col-sm-offset-3 col-xs-10 col-xs-offset-1',
                onOpen: function(){},
                onClose: function(){},
                onAction: function(){}
            };
        </script>
    """
    js = f"""<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery-confirm/{kwargs.get('version', '3.3.4')}/jquery-confirm.min.js" integrity="sha512-zP5W8791v1A6FToy+viyoyUUyjCzx+4K8XZCKzW28AnCoepPNIXecxh9mvGuy3Rt78OzEsU+VCvcObwAMvBAww==" crossorigin="anonymous"></script>"""
    css = f"""<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jquery-confirm/{kwargs.get('version', '3.3.4')}/jquery-confirm.min.css" integrity="sha512-0V10q+b1Iumz67sVDL8LPFZEEavo6H/nBSyghr7mm9JEQkOAm91HNoZQRvQdjennBb/oEuW+8oZHVpIKq+d25g==" crossorigin="anonymous" />"""
    return f"""
    {js}
    {css}
    {defaults}
    """


def chosen(*args, **kwargs):
    return format_html(
        f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/chosen/1.8.7/chosen.min.css" 
            integrity="sha512-yVvxUQV0QESBt1SyZbNJMAwyKvFTLMyXSyBHDO4BG5t7k/Lw34tyqlSDlKIrIENIzCl+RVUNjmCPG+V/GMesRw==" 
            crossorigin="anonymous" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/chosen/1.8.7/chosen.jquery.min.js" 
            integrity="sha512-rMGGF4wg1R73ehtnxXBt5mbUfN9JUJwbk21KMlnLZDJh7BkPmeovBuddZCENJddHYYMkCh9hPFnPmS9sspki8g==" 
            crossorigin="anonymous"></script>
        <script src="{mjg_url()}/js/chosen-apply.js"></script>
        """
    )


def font_awesome(*args, **kwargs):
    version = kwargs.get('version', 'current')
    url = f"{lib_url()}/fontawesome/{version}"

    # FontAwesome 4 is CSS rather than SVG
    if version == '4':
        return format_html(
            f"""<link rel="stylesheet" href="{url}/css/font-awesome.min.css" />"""
        )

    else:
        return format_html(
            f"""<script defer src="{url}/js/all.js"></script>"""
        )


def cdn_css(*args, **kwargs):
    version = kwargs.get('version', 'v1')
    url = f"{mjg_url(version)}/css"
    return format_html("\n".join([f"""<link rel="stylesheet" href="{url}/{css}" />""" for css in args]))


def cdn_js(*args, **kwargs):
    version = kwargs.get('version', 'v1')
    url = f"{mjg_url(version)}/js"
    return format_html("\n".join([f"""<script src="{url}/{js}"></script>""" for js in args]))
