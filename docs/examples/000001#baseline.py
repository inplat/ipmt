from ipmt.db import transactional, SERIALIZABLE


@transactional(isolation_level=SERIALIZABLE)
def up(db):
    """
    :type db: ipmt.db.Database
    """
    db.execute("""\
        CREATE SCHEMA myschema;
    """)


@transactional(isolation_level=SERIALIZABLE)
def down(db):
    """
    :type db: ipmt.db.Database
    """
    db.execute("""\
        DROP SCHEMA myschema;
    """)
