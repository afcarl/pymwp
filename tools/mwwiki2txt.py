#!/usr/bin/env python
#
# Usage examples:
#  $ mwwiki2txt.py article12.wiki > article12.txt
#  $ mwwiki2txt.py -L article12.wiki > article12.link
#  $ mwwiki2txt.py -Z -o jawiki.txt.cdb jawiki.xml.bz2
#  $ mwwiki2txt.py -Z -o jawiki.txt.cdb jawiki.wiki.cdb
#  $ mwwiki2txt.py -o all.txt.bz2 jawiki.xml.bz2
#  $ mwwiki2txt.py -P 'article%(pageid)08d.txt' jawiki.xml.bz2
#
import re
import sys
from pymwp.mwtokenizer import WikiToken
from pymwp.mwtokenizer import XMLTagToken
from pymwp.mwtokenizer import XMLEmptyTagToken
from pymwp.mwparser import WikiTextParser
from pymwp.mwparser import WikiTree
from pymwp.mwparser import WikiXMLTree
from pymwp.mwparser import WikiArgTree
from pymwp.mwparser import WikiSpecialTree
from pymwp.mwparser import WikiCommentTree
from pymwp.mwparser import WikiKeywordTree
from pymwp.mwparser import WikiLinkTree
from pymwp.mwparser import WikiDivTree
from pymwp.mwparser import WikiTableTree
from pymwp.mwparser import WikiTableCellTree
from pymwp.mwparser import WikiParserError
from pymwp.mwxmldump import MWXMLDumpFilter
from pymwp.mwcdb import WikiDBReader
from pymwp.mwcdb import WikiDBWriter
from pymwp.mwcdb import WikiFileWriter
from pymwp.utils import getfp


SPC = re.compile(r'\s+')
def rmsp(s): return SPC.sub(' ', s)

IGNORED = re.compile(u'^([-a-z]+|Category|Special):')
def isignored(name): return IGNORED.match(name)


##  WikiTextExtractor
##
class WikiTextExtractor(WikiTextParser):

    def __init__(self, errfp=None):
        WikiTextParser.__init__(self)
        self.errfp = errfp
        return

    def error(self, s):
        if self.errfp is not None:
            self.errfp.write(s+'\n')
        return

    def invalid_token(self, pos, token):
        self.error('invalid token(%d): %r' % (pos, token))
        return

    def close(self):
        WikiTextParser.close(self)
        texts = self.convert(self.get_root())
        return u''.join(texts)

    def convert(self, tree):
        if tree is WikiToken.PAR:
            yield u'\n'
        elif isinstance(tree, XMLEmptyTagToken):
            if tree.name in XMLTagToken.BR_TAG:
                yield u'\n'
        elif isinstance(tree, unicode):
            yield rmsp(tree)
        elif isinstance(tree, WikiToken):
            yield rmsp(tree.name)
        elif isinstance(tree, WikiSpecialTree):
            pass
        elif isinstance(tree, WikiCommentTree):
            pass
        elif isinstance(tree, WikiXMLTree):
            if tree.xml.name in XMLTagToken.NO_TEXT:
                pass
            else:
                for c in tree:
                    for x in self.convert(c):
                        yield x
                if tree.xml.name in XMLTagToken.PAR_TAG:
                    yield u'\n'
        elif isinstance(tree, WikiKeywordTree):
            if tree:
                if isinstance(tree[0], WikiTree):
                    name = tree[0].get_text()
                else:
                    name = tree[0]
                if isinstance(name, unicode) and not isignored(name):
                    for x in self.convert(tree[-1]):
                        yield x
        elif isinstance(tree, WikiLinkTree):
            if 2 <= len(tree):
                for c in tree[1:]:
                    for x in self.convert(c):
                        yield x
                    yield u' '
            elif tree:
                for x in self.convert(tree[0]):
                    yield x
        elif isinstance(tree, WikiTableCellTree):
            if tree:
                for x in self.convert(tree[-1]):
                    yield x
                yield u'\n'
        elif isinstance(tree, WikiTableTree):
            for c in tree:
                if not isinstance(c, WikiArgTree):
                    for x in self.convert(c):
                        yield x
        elif isinstance(tree, WikiDivTree):
            for c in tree:
                for x in self.convert(c):
                    yield x
            yield u'\n'
        elif isinstance(tree, WikiTree):
            for c in tree:
                for x in self.convert(c):
                    yield x
        return


##  WikiLinkExtractor
##
class WikiLinkExtractor(WikiTextParser):

    def __init__(self, errfp=None):
        WikiTextParser.__init__(self)
        self.errfp = errfp
        return

    def error(self, s):
        if self.errfp is not None:
            self.errfp.write(s+'\n')
        return

    def invalid_token(self, pos, token):
        self.error('invalid token(%d): %r' % (pos, token))
        return

    def close(self):
        WikiTextParser.close(self)
        texts = self.convert(self.get_root())
        return u''.join(texts)

    def convert(self, tree):
        if isinstance(tree, WikiKeywordTree):
            if tree:
                if isinstance(tree[0], WikiTree):
                    name = tree[0].get_text()
                else:
                    name = tree[0]
                if isinstance(name, unicode):
                    out = (u'keyword', name)
                    if 2 <= len(tree) and not isignored(name):
                        text = tree[-1].get_text()
                        out += (text,)
                    yield u'\t'.join(out)+u'\n'
        elif isinstance(tree, WikiLinkTree):
            if tree:
                if isinstance(tree[0], WikiTree):
                    url = tree[0].get_text()
                else:
                    url = tree[0]
                if isinstance(url, unicode):
                    out = (u'link', url)
                    if 2 <= len(tree):
                        text = tree[-1].get_text()
                        out += (text,)
                    yield u'\t'.join(out)+u'\n'
        elif isinstance(tree, WikiTree):
            for c in tree:
                for x in self.convert(c):
                    yield x
        return


##  WikiCategoryExtractor
##
class WikiCategoryExtractor(WikiTextParser):

    def __init__(self, errfp=None):
        WikiTextParser.__init__(self)
        self.errfp = errfp
        return

    def error(self, s):
        if self.errfp is not None:
            self.errfp.write(s+'\n')
        return

    def invalid_token(self, pos, token):
        self.error('invalid token(%d): %r' % (pos, token))
        return

    def close(self):
        WikiTextParser.close(self)
        texts = self.convert(self.get_root())
        return u'\t'.join(texts)

    def convert(self, tree):
        if isinstance(tree, WikiKeywordTree):
            if tree:
                if isinstance(tree[0], WikiTree):
                    name = tree[0].get_text()
                else:
                    name = tree[0]
                if isinstance(name, unicode) and name.startswith('Category:'):
                    yield name
        elif isinstance(tree, WikiTree):
            for c in tree:
                for x in self.convert(c):
                    yield x
        return


##  MWDump2Text
##
class MWDump2Text(MWXMLDumpFilter):

    def __init__(self, converter):
        MWXMLDumpFilter.__init__(self)
        self.converter = converter
        return

    def start_page(self, pageid, title):
        MWXMLDumpFilter.start_page(self, pageid, title)
        pageid = int(pageid)
        self.converter.add_page(pageid, title)
        return

    def open_file(self, pageid, title, revid, timestamp):
        pageid = int(pageid)
        revid = int(pageid)
        self.converter.add_revid(pageid, revid)
        return self._Stream(pageid, revid)
    
    def close_file(self, fp):
        self.converter.feed_text(fp.pageid, fp.revid, u''.join(fp.text))
        return
    
    def write_file(self, fp, text):
        fp.text.append(text)
        return

    class _Stream(object):
        def __init__(self, pageid, revid):
            self.pageid = pageid
            self.revid = revid
            self.text = []
            return


##  Converter
##
class Converter(object):
    
    def __init__(self, writer, klass, errfp=None):
        self.writer = writer
        self.klass = klass
        self.errfp = errfp
        return

    def close(self):
        return

    def error(self, s):
        if self.errfp is not None:
            self.errfp.write(s+'\n')
        return
        
    def add_page(self, pageid, title):
        print >>sys.stderr, (pageid, title)
        self.writer.add_page(pageid, title)
        return
        
    def add_revid(self, pageid, revid):
        self.writer.add_revid(pageid, revid)
        return
        
    def feed_text(self, pageid, revid, text):
        parser = self.klass(errfp=self.errfp)
        try:
            parser.feed_text(text)
            self.writer.add_text(pageid, revid, parser.close())
        except WikiParserError, e:
            self.error('error: %r' % e)
        return
        
    def feed_file(self, pageid, revid, fp, codec='utf-8'):
        parser = self.klass(errfp=self.errfp)
        try:
            parser.feed_file(fp, codec=codec)
            self.writer.add_text(pageid, revid, parser.close())
        except WikiParserError, e:
            self.error('error: %r' % e)
        return

# main
def main(argv):
    import getopt
    def usage():
        print ('usage: %s [-L|-C] [-d] [-o output] [-P pathpat] [-c codec] [-T] [-Z] '
               '[file ...]') % argv[0]
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'LCdo:P:c:m:TZ')
    except getopt.GetoptError:
        return usage()
    args = args or ['-']
    errfp = None
    output = '-'
    codec = 'utf-8'
    ext = ''
    pathpat = None
    mode = 'page'
    titleline = False
    klass = WikiTextExtractor
    for (k, v) in opts:
        if k == '-d': errfp = sys.stderr
        elif k == '-o': output = v
        elif k == '-P': pathpat = v
        elif k == '-c': codec = v 
        elif k == '-m': mode = v 
        elif k == '-T': titleline = True
        elif k == '-Z': ext = '.gz'
        elif k == '-L': klass = WikiLinkExtractor
        elif k == '-C': klass = WikiCategoryExtractor
    if output.endswith('.cdb'):
        writer = WikiDBWriter(output, codec=codec, ext=ext)
    else:
        writer = WikiFileWriter(
            output=output, pathpat=pathpat,
            codec=codec, titleline=titleline, mode=mode)
    try:
        converter = Converter(writer, klass, errfp=errfp)
        for path in args:
            if path.endswith('.cdb'):
                reader = WikiDBReader(path, codec=codec, ext=ext)
                for pageid in reader:
                    (title, revids) = reader[pageid]
                    converter.add_page(pageid, title)
                    for revid in revids:
                        wiki = reader.get_wiki(pageid, revid)
                        converter.add_revid(pageid, revid)
                        converter.feed_text(pageid, revid, wiki)
            else:
                (path,fp) = getfp(path)
                if path.endswith('.xml'):
                    parser = MWDump2Text(converter)
                    parser.feed_file(fp)
                    parser.close()
                else:
                    converter.add_page(0, path)
                    converter.add_revid(0, 0)
                    converter.feed_file(0, 0, fp, codec=codec)
                fp.close()
        converter.close()
    finally:
        writer.close()
    return

if __name__ == '__main__': sys.exit(main(sys.argv))
