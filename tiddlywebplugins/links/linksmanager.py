"""
Module to contain the LinksManager class.
"""

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import mapper, sessionmaker, scoped_session
from sqlalchemy.schema import (Table, Column, PrimaryKeyConstraint,
        MetaData)
from sqlalchemy.types import Unicode

from tiddlywebplugins.links.parser import process_tiddler, is_link

DB_DEFAULT = 'sqlite:///links.db'

METADATA = MetaData()
SESSION = scoped_session(sessionmaker())

LINK_TABLE = Table('link', METADATA,
        Column('source', Unicode(100), nullable=False,
            index=True, primary_key=True),
        Column('target', Unicode(233), nullable=False,
            index=True, primary_key=True),
        mysql_charset='utf8')


class SLink(object):
    """
    Holder object for mapping the Link. Kind of redundant
    but nice for the __repr__.
    """

    def __init__(self, source, target):
        object.__init__(self)
        self.source = source
        self.target = target

    def __repr__(self):
        return '<SLink(%s->%s)>' % (self.source, self.target)

mapper(SLink, LINK_TABLE)

ENGINE = None
MAPPED = False


class LinksManager(object):
    """
    A container class for the functionality for managing a
    front and backlinks database. The primary purpose is to
    encapsulate an 'environ' and provide the forward opportunity
    to subclass for different types of storage.
    """

    def __init__(self, environ=None):
        """
        Establish an environ for this instance.
        """

        global ENGINE, MAPPED

        if environ is None:
            environ = {}
        self.environ = environ

        if not ENGINE:
            db_config = self._db_config()
            if 'mysql' in db_config:
                try:
                    from tiddlywebplugins.mysql2 import LookLively
                    listeners = [LookLively()]
                except ImportError:
                    listeners = []
                ENGINE = create_engine(db_config,
                        pool_recycle=3600,
                        pool_size=20,
                        max_overflow=-1,
                        pool_timeout=2,
                        listeners=listeners)
            else:
                ENGINE = create_engine(db_config)
            METADATA.bind = ENGINE
            SESSION.configure(bind=ENGINE)

        self.session = SESSION()

        if not MAPPED:
            METADATA.create_all(ENGINE)
            MAPPED = True

    def _db_config(self):
        """
        Extract the database configuration from config or use
        the default.
        """
        return self.environ.get('tiddlyweb.config', {}).get(
                'linkdb_config', DB_DEFAULT)

    def update_database(self, tiddler):
        """
        Update the front and back links databases with the provided
        tiddler.
        """
        links = process_tiddler(tiddler)
        self._update_links(links, tiddler)

    def read_frontlinks(self, tiddler):
        """
        Return a list of forward links from this tiddler.
        """
        source = _tiddler_key(tiddler)

        try:
            links = self.session.query(SLink.target).filter(
                    SLink.source == source).all()
            self.session.close()
        except:
            self.session.rollback()
            raise
        return [link[0] for link in links]

    def read_backlinks(self, tiddler):
        """
        Return a list of links to this tiddler.
        """
        target = _tiddler_key(tiddler)

        try:
            links = self.session.query(SLink.source).filter(
                    SLink.target == target).all()
            self.session.close()
        except:
            self.session.rollback()
            raise
        return [link[0] for link in links]

    def delete_links(self, tiddler):
        """
        Clean out the links for this tiddler.
        """
        source = _tiddler_key(tiddler)

        try:
            old_links = self.session.query(SLink).filter(
                    SLink.source == source)
            old_links.delete()
        except:
            self.session.rollback()
            raise

    def _update_links(self, links, tiddler):
        """
        Update the links database.
        """
        source = _tiddler_key(tiddler)

        try:
            for link, space in links:
                if link is None:
                    link = ''
                if is_link(link):
                    target = link
                elif space:
                    target = '%s_public:%s' % (space, link)
                else:
                    target = '%s:%s' % (tiddler.bag, link)
                new_link = SLink(source, target)
                self.session.merge(new_link)
            self.session.commit()
        except:
            self.session.rollback()
            raise


def _tiddler_key(tiddler):
    """
    Generate a source or target key from a tiddler object.
    """
    return '%s:%s' % (tiddler.bag, tiddler.title)
