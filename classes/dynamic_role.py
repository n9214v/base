contact_admin_roles = ['admin', 'contact_admin']
security_admin_roles = ['admin', 'security_admin']

power_user_roles = ['security_admin', 'admin', 'developer']
super_user_roles = ['developer']

impersonation_roles = ['developer']
proxy_roles = ['admin', 'proxy']


class DynamicRole:

    @staticmethod
    def get(role_string):
        if '~' not in role_string:
            return [role_string]

        if 'power' in role_string:
            return power_user_roles

        if 'super' in role_string:
            return super_user_roles

        if 'imperson' in role_string:
            return impersonation_roles
        if 'contact' in role_string:
            return contact_admin_roles
        if 'security' in role_string:
            return security_admin_roles
        if 'proxy' in role_string:
            return proxy_roles

        return []

    def __init__(self):
        pass
