import logging
import os
from os.path import dirname, normpath, relpath, join
 
from pyjade import Compiler as _Compiler, Parser, register_filter
from pyjade.runtime import attrs
from pyjade.exceptions import CurrentlyNotSupported
from pyjade.utils import process

from django.conf import settings

logger = logging.getLogger(__name__)

class Compiler(_Compiler):
    autocloseCode = 'if,ifchanged,ifequal,ifnotequal,for,block,filter,autoescape,with,trans,blocktrans,spaceless,comment,cache,localize,compress,verbatim'.split(',')
    useRuntime = True

    def __init__(self, node, **options):
        self.origin = options.get('origin', None)
        if settings.configured:
            options.update(getattr(settings,'PYJADE',{}))
        super(Compiler, self).__init__(node, **options)

    def visitCodeBlock(self,block):
        self.buffer('{%% block %s %%}'%block.name)
        if block.mode=='append': self.buffer('{{block.super}}')
        self.visitBlock(block)
        if block.mode=='prepend': self.buffer('{{block.super}}')
        self.buffer('{% endblock %}')

    def visitAssignment(self,assignment):
        self.buffer('{%% __pyjade_set %s = %s %%}'%(assignment.name,assignment.val))

    def visitMixin(self,mixin):
        self.mixing += 1
        if not mixin.call:
          self.buffer('{%% __pyjade_kwacro %s %s %%}'%(mixin.name,mixin.args)) 
          self.visitBlock(mixin.block)
          self.buffer('{% end__pyjade_kwacro %}')
        elif mixin.block:
          raise CurrentlyNotSupported("The mixin blocks are not supported yet.")
        else:
          self.buffer('{%% __pyjade_usekwacro %s %s %%}'%(mixin.name,mixin.args))
        self.mixing -= 1

    def visitCode(self,code):
        if code.buffer:
            val = code.val.lstrip()
            val = self.var_processor(val)
            self.buf.append('{{%s%s}}'%(val,'|force_escape' if code.escape else ''))
        else:
            self.buf.append('{%% %s %%}'%code.val)

        if code.block:
            self.visit(code.block)

            if not code.buffer:
              codeTag = code.val.strip().split(' ',1)[0]
              if codeTag in self.autocloseCode:
                  self.buf.append('{%% end%s %%}'%codeTag)

    def attributes(self,attrs):
        return "{%% __pyjade_attrs %s %%}"%attrs

    def make_relative(self, path):
        dirname_ = dirname(self.origin.name)
        abspath_ = normpath(join(dirname_, path))
        logger.debug('Abspath: ' + abspath_)
        root = next(d for d in settings.TEMPLATE_DIRS if abspath_.startswith(d))
        logger.debug('Root: ' + root)
        relpath_ = relpath(abspath_, start=root)
        logger.debug('Relpath: ' + relpath_ + '\n')
        return relpath_

    def visitExtends(self, node):
        node.path = self.make_relative(node.path)
        super(Compiler, self).visitExtends(node)

    def visitInclude(self, node):
        node.path = self.make_relative(node.path)
        super(Compiler, self).visitInclude(node)


from django import template
template.add_to_builtins('pyjade.ext.django.templatetags')

from django.utils.translation import trans_real

try:
    from django.utils.encoding import force_text as to_text
except ImportError:
    from django.utils.encoding import force_unicode as to_text

def decorate_templatize(func):
    def templatize(src, origin=None):
        src = to_text(src, settings.FILE_CHARSET)
        html = process(src,compiler=Compiler)
        return func(html, origin)

    return templatize

trans_real.templatize = decorate_templatize(trans_real.templatize)

try:
    from django.contrib.markup.templatetags.markup import markdown

    @register_filter('markdown')
    def markdown_filter(x,y):
        return markdown(x)
        
except ImportError:
    pass

