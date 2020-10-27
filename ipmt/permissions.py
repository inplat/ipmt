# -*- coding: utf-8 -*-
import re
import logging
import yaml
from yaml import Dumper
from collections import OrderedDict
from functools import reduce
from ipmt.db import Database, Transaction


def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


Dumper.add_representer(OrderedDict, dict_representer)

ACL_INSERT = 1 << 0  # for relations */
ACL_SELECT = 1 << 1
ACL_UPDATE = 1 << 2
ACL_DELETE = 1 << 3
ACL_TRUNCATE = 1 << 4
ACL_REFERENCES = 1 << 5
ACL_TRIGGER = 1 << 6
ACL_EXECUTE = 1 << 7  # for functions */
ACL_USAGE = 1 << 8  # for languages, namespaces, FDWs, and * servers
ACL_CREATE = 1 << 9  # for namespaces and databases */
ACL_CREATE_TEMP = 1 << 10  # for databases */
ACL_CONNECT = 1 << 11  # for databases */
N_ACL_RIGHTS = 12  # 1 plus the last 1<<x */
ACL_NO_RIGHTS = 0
ACL_SELECT_FOR_UPDATE = ACL_UPDATE

ACL_INSERT_CHR = "a"  # formerly known as "append"
ACL_SELECT_CHR = "r"  # formerly known as "read"
ACL_UPDATE_CHR = "w"  # formerly known as "write"
ACL_DELETE_CHR = "d"
ACL_TRUNCATE_CHR = "D"  # super-delete, as it were
ACL_REFERENCES_CHR = "x"
ACL_TRIGGER_CHR = "t"
ACL_EXECUTE_CHR = "X"
ACL_USAGE_CHR = "U"
ACL_CREATE_CHR = "C"
ACL_CREATE_TEMP_CHR = "T"
ACL_CONNECT_CHR = "c"

ACL_ALL_RIGHTS_COLUMN = ACL_INSERT | ACL_SELECT | ACL_UPDATE | ACL_REFERENCES
ACL_ALL_RIGHTS_RELATION = (
    ACL_INSERT
    | ACL_SELECT
    | ACL_UPDATE
    | ACL_DELETE
    | ACL_TRUNCATE
    | ACL_REFERENCES
    | ACL_TRIGGER
)
ACL_ALL_RIGHTS_SEQUENCE = ACL_USAGE | ACL_SELECT | ACL_UPDATE
ACL_ALL_RIGHTS_DATABASE = ACL_CREATE | ACL_CREATE_TEMP | ACL_CONNECT
ACL_ALL_RIGHTS_FDW = ACL_USAGE
ACL_ALL_RIGHTS_FOREIGN_SERVER = ACL_USAGE
ACL_ALL_RIGHTS_FUNCTION = ACL_EXECUTE
ACL_ALL_RIGHTS_LANGUAGE = ACL_USAGE
ACL_ALL_RIGHTS_LARGEOBJECT = ACL_SELECT | ACL_UPDATE
ACL_ALL_RIGHTS_NAMESPACE = ACL_USAGE | ACL_CREATE
ACL_ALL_RIGHTS_TABLESPACE = ACL_CREATE
ACL_ALL_RIGHTS_TYPE = ACL_USAGE

RELKIND_NAMESPACE = "n"
RELKIND_FUNCTION = "F"  # function
RELKIND_TABLE = "r"
RELKIND_SEQUENCE = "S"  # sequence object
RELKIND_VIEW = "v"  # view
RELKIND_FOREIGN_TABLE = "f"  # foreign table
RELKIND_MATVIEW = "m"  # materialized view

acl_aliases = {
    "none": [],
    "select": [ACL_SELECT],
    "update": [ACL_UPDATE],
    "insert": [ACL_INSERT],
    "delete": [ACL_DELETE],
    "truncate": [ACL_TRUNCATE],
    "references": [ACL_REFERENCES],
    "trigger": [ACL_TRIGGER],
    "execute": [ACL_EXECUTE],
    "usage": [ACL_USAGE],
    "create": [ACL_CREATE],
    "connect": [ACL_CONNECT],
    "temporary": [ACL_CREATE_TEMP],
    "all": (
        [
            ACL_INSERT,
            ACL_SELECT,
            ACL_UPDATE,
            ACL_DELETE,
            ACL_TRUNCATE,
            ACL_REFERENCES,
            ACL_TRIGGER,
            ACL_EXECUTE,
            ACL_USAGE,
            ACL_CREATE,
            ACL_CREATE_TEMP,
            ACL_CONNECT,
        ]
    ),
}


def get_db(dsn):
    return Database(dsn)


def update(dsn, file, roles, exclude, dry_run):
    acl_conf = config_load(file, roles, exclude)
    db = get_db(dsn)
    acl = load_acl(db, acl_conf.get("exclude"), acl_conf.get("roles"))
    diff = make_diff(acl, acl_conf)
    queries = get_diff_sql(diff)
    db.dry_run = dry_run
    if queries:
        with Transaction(db=db):
            for query in queries:
                db.execute(query)
    return "\n".join(db.buffer)


def investigate(dsn, file, roles, exclude):
    db = get_db(dsn)
    acl = load_acl(db, exclude, roles)
    result = {"objects": OrderedDict()}
    if exclude:
        result["exclude"] = sorted(exclude)
    result_roles = roles or []
    for obj, obj_acl, obj_kind in acl:
        obj_perms = OrderedDict()
        for role, role_perms in obj_acl.items():
            if not roles or role in roles:
                perms = privileges_to_short_string(role_perms, obj_kind)
                if perms:
                    obj_perms[role] = ", ".join(perms)
            if not roles and role not in result_roles:
                result_roles.append(role)
        if obj_perms:
            result["objects"][obj] = obj_perms

    result["roles"] = sorted(result_roles)
    yaml.dump(result, file, default_flow_style=False, Dumper=Dumper)


def make_diff(db_acl, conf):
    diff = []
    for obj, obj_acl, obj_kind in db_acl:
        if "objects" in conf:
            obj_conf_acl = None
            for pattern in conf["objects"].keys():
                if pattern[0:1] == "~":
                    regex = re.compile("^%s$" % pattern[1:])
                    match = regex.match(obj)
                else:
                    match = pattern == obj
                if match:
                    obj_conf_acl = merge_dicts(
                        conf["objects"][pattern], obj_conf_acl or OrderedDict()
                    )
            obj_conf_acl = obj_conf_acl or OrderedDict()

            obj_db_acl = OrderedDict()
            for role in obj_acl.keys():
                if role in conf["roles"]:
                    obj_db_acl[role] = obj_acl[role]

            diff.append((obj, obj_kind, dict_diff(obj_db_acl, obj_conf_acl)))
    return diff


def get_diff_sql(diff):
    queries = []
    for obj, obj_kind, acl_diff in diff:
        for role in acl_diff:
            for type, sql_1, sql_2 in (
                ("+", "GRANT", "TO"),
                ("-", "REVOKE", "FROM"),
            ):
                perms = []
                for perm in acl_diff[role][type]:
                    if validate_privilege(perm, obj_kind):
                        perms.append(privilege_to_string(perm))
                if perms:
                    sql = "%s %s ON %s %s %s %s;" % (
                        sql_1,
                        ",".join(perms),
                        char_to_rel_name(obj_kind),
                        obj,
                        sql_2,
                        role,
                    )
                    queries.append(sql)
    return queries


def merge_dicts(dict1, dict2):
    res = dict1.copy()
    for key in dict2:
        if key in res:
            for val in dict2[key]:
                if val not in res[key]:
                    res[key].append(val)
        else:
            res[key] = dict2[key]
    return res


def dict_diff(dict1, dict2):
    result = OrderedDict()
    keys = set(list(dict1.keys()) + list(dict2.keys()))
    for role in keys:
        result[role] = OrderedDict([("+", []), ("-", [])])
        if role in dict1 and role not in dict2:
            result[role]["-"] = dict1[role]
        elif role not in dict1 and role in dict2:
            result[role]["+"] = dict2[role]
        else:
            result[role]["-"] = list(set(dict1[role]) - set(dict2[role]))
            result[role]["+"] = list(set(dict2[role]) - set(dict1[role]))
    return result


def load_acl(db, exclude, roles):
    sql = """\
SELECT
        pg_namespace.nspname::text,
        pg_class.relname::text,
        pg_class.relacl::text[],
        pg_class.relkind
FROM
        pg_class
JOIN
        pg_namespace ON relnamespace = pg_namespace.oid
WHERE
        substring(nspname, 1, 3) <> 'pg_'
        AND
        substring(nspname, 1, 3) <> 'gp_'
        AND
        nspname <> 'information_schema'
        AND
        relkind IN ('r', 'S', 'v', 'm', 'f')
UNION
SELECT
        nspname::text,
        NULL::text,
        nspacl::text[],
        'n'
FROM
        pg_namespace
WHERE
        substring(nspname, 1, 3) <> 'pg_'
        AND
        substring(nspname, 1, 3) <> 'gp_'
        AND
        nspname <> 'information_schema'
UNION
SELECT
        nspname::text,
        quote_ident(proname) || '('
                             || oidvectortypes(proargtypes)::text || ')',
        proacl::text[],
        'F'
FROM
        pg_proc
JOIN
        pg_namespace ON pronamespace = pg_namespace.oid
WHERE
        substring(nspname, 1, 3) <> 'pg_'
        AND
        substring(nspname, 1, 3) <> 'gp_'
        AND
        nspname <> 'information_schema'
ORDER BY nspname, relname
        """
    result = []
    for row in db.query_all(sql):
        object_name = get_object_name(row[0], row[1], row[3])
        if not is_exclude(object_name, exclude):
            result.append([object_name, parser_acl(row[2], roles), row[3]])
    return result


def is_exclude(name, conf):
    if not conf:
        return False
    for item in conf:
        if item[0:1] == "~":
            regex = re.compile("^%s$" % item[1:])
            match = regex.match(name)
        else:
            match = item == name
        if match:
            return True
    return False


def get_object_name(schema, name, relkind):
    if relkind == RELKIND_NAMESPACE:
        return schema
    # if schema == 'public':
    #     return name
    return "%s.%s" % (schema, name)


def privilege_to_string(privilege):
    if privilege == ACL_INSERT:
        return "INSERT"
    elif privilege == ACL_SELECT:
        return "SELECT"
    elif privilege == ACL_UPDATE:
        return "UPDATE"
    elif privilege == ACL_DELETE:
        return "DELETE"
    elif privilege == ACL_TRUNCATE:
        return "TRUNCATE"
    elif privilege == ACL_REFERENCES:
        return "REFERENCES"
    elif privilege == ACL_TRIGGER:
        return "TRIGGER"
    elif privilege == ACL_EXECUTE:
        return "EXECUTE"
    elif privilege == ACL_USAGE:
        return "USAGE"
    elif privilege == ACL_CREATE:
        return "CREATE"
    elif privilege == ACL_CREATE_TEMP:
        return "TEMP"
    elif privilege == ACL_CONNECT:
        return "CONNECT"
    else:
        raise NotImplementedError('Unknown privilege "%s"' % privilege)


def privileges_to_short_string(privileges, relkind):
    acl = [char for char in privileges if validate_privilege(char, relkind)]
    if is_all_privileges(reduce(lambda a, b: a | b, acl), relkind):
        return ["all"]
    return [privilege_to_string(privilege).lower() for privilege in acl]


def char_to_privilege(char):
    if char == ACL_INSERT_CHR:
        return ACL_INSERT
    elif char == ACL_SELECT_CHR:
        return ACL_SELECT
    elif char == ACL_UPDATE_CHR:
        return ACL_UPDATE
    elif char == ACL_DELETE_CHR:
        return ACL_DELETE
    elif char == ACL_TRUNCATE_CHR:
        return ACL_TRUNCATE
    elif char == ACL_REFERENCES_CHR:
        return ACL_REFERENCES
    elif char == ACL_TRIGGER_CHR:
        return ACL_TRIGGER
    elif char == ACL_EXECUTE_CHR:
        return ACL_EXECUTE
    elif char == ACL_USAGE_CHR:
        return ACL_USAGE
    elif char == ACL_CREATE_CHR:
        return ACL_CREATE
    elif char == ACL_CREATE_TEMP_CHR:
        return ACL_CREATE_TEMP
    elif char == ACL_CONNECT_CHR:
        return ACL_CONNECT
    else:
        raise NotImplementedError('Unknown privilege char "%s"' % char)


def char_to_rel_name(char):
    if char == RELKIND_NAMESPACE:
        return "SCHEMA"
    elif char == RELKIND_TABLE:
        return "TABLE"
    elif char == RELKIND_SEQUENCE:
        return "SEQUENCE"
    elif char == RELKIND_VIEW:
        return "TABLE"
    elif char == RELKIND_FOREIGN_TABLE:
        return "TABLE"
    elif char == RELKIND_MATVIEW:
        return "TABLE"
    elif char == RELKIND_FUNCTION:
        return "FUNCTION"
    else:
        raise NotImplementedError('Unknown object char "%s"' % char)


def validate_privilege(privilege, relkind):
    if relkind == RELKIND_NAMESPACE:
        return privilege & ACL_ALL_RIGHTS_NAMESPACE
    elif relkind == RELKIND_TABLE:
        return privilege & ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_VIEW:
        return privilege & ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_MATVIEW:
        return privilege & ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_FOREIGN_TABLE:
        return privilege & ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_SEQUENCE:
        return privilege & ACL_ALL_RIGHTS_SEQUENCE
    elif relkind == RELKIND_FUNCTION:
        return privilege & ACL_ALL_RIGHTS_FUNCTION
    return False


def is_all_privileges(privileges, relkind):
    if relkind == RELKIND_NAMESPACE:
        return privileges == ACL_ALL_RIGHTS_NAMESPACE
    elif relkind == RELKIND_TABLE:
        return privileges == ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_VIEW:
        return privileges == ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_MATVIEW:
        return privileges == ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_FOREIGN_TABLE:
        return privileges == ACL_ALL_RIGHTS_RELATION
    elif relkind == RELKIND_SEQUENCE:
        return privileges == ACL_ALL_RIGHTS_SEQUENCE
    elif relkind == RELKIND_FUNCTION:
        return privileges == ACL_ALL_RIGHTS_FUNCTION
    return False


def parser_acl(acl, roles):
    result = {}
    if acl is not None:
        if not isinstance(acl, list):
            acl = acl.strip("{}").split(",")
        for item in acl:
            if not item:
                continue
            role, perm = item.split("=")
            permisions, grantor = perm.split("/")
            if roles is None or role in roles:
                result[role or "public"] = [
                    char_to_privilege(char) for char in list(permisions)
                ]
    return result


def config_load(file, roles, exclude):
    conf = yaml.safe_load(file)
    if not conf:
        logging.warning("Empty permissions config")
        return {}
    conf["roles"] = set(roles or conf.get("roles", []))
    if not conf["roles"]:
        raise UserWarning('You must specify "roles"')
    if "objects" in conf:
        for obj, perms in conf["objects"].items():
            for rolename in list(perms.keys()):
                if rolename in conf["roles"]:
                    perms_list = [
                        perm_str.strip().lower()
                        for perm_str in perms[rolename].split(",")
                    ]
                    perms[rolename] = []
                    for perm_str in perms_list:
                        if perm_str not in acl_aliases:
                            raise UserWarning(
                                'Unknown permission "%s"' % perm_str
                            )
                        perms[rolename] += acl_aliases[perm_str]
                else:
                    perms.pop(rolename)
    else:
        conf["objects"] = []

    exclude = exclude or conf.get("exclude") or []
    if exclude:
        if not isinstance(exclude, list):
            raise UserWarning("Invalid format of exclude condition")
    conf["exclude"] = exclude
    return conf
