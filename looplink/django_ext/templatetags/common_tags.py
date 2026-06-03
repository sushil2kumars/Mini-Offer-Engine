import json

from django import template
from django.conf import settings
from django.template import NodeList, TemplateSyntaxError, loader_tags

register = template.Library()


# https://djangosnippets.org/snippets/545/
@register.tag(name="captureas")
def do_captureas(parser, token):
    """
    Assign to a context variable from within a template
        {% captureas my_context_var %}<!-- anything -->{% endcaptureas %}
        <h1>Nice job capturing {{ my_context_var }}</h1>
    """
    try:
        tag_name, args = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError("'captureas' node requires a variable name.")
    nodelist = parser.parse(("endcaptureas",))
    parser.delete_first_token()
    return CaptureasNode(nodelist, args)


class CaptureasNode(template.Node):
    def __init__(self, nodelist, varname):
        self.nodelist = nodelist
        self.varname = varname

    def render(self, context):
        output = self.nodelist.render(context)
        context[self.varname] = output
        return ""


@register.filter
def JSON(obj):
    return json.dumps(obj)


@register.filter
def BOOL(obj):
    try:
        obj = obj.to_json()
    except AttributeError:
        pass

    return "true" if obj else "false"


@register.filter
@register.simple_tag
def static(url):
    return settings.STATIC_URL + url


def _bundler_main(parser, token, flag, node_class):
    bits = token.contents.split(None, 1)
    if len(bits) == 1:
        tag_name = bits[0]
        value = None
    else:
        tag_name, value = bits

    if getattr(parser, flag, False):
        raise TemplateSyntaxError("multiple '{}' tags not allowed ({})".format(*tuple(bits)))
    setattr(parser, flag, True)

    if value and (len(value) < 2 or value[0] not in "\"'" or value[0] != value[-1]):
        raise TemplateSyntaxError("bad '{}' argument: {}".format(*tuple(bits)))

    # use a block to allow extension template to set <bundler>_main for base
    return loader_tags.BlockNode("__" + tag_name, NodeList([node_class(tag_name, value and value[1:-1])]))


class WebpackMainNode(template.Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.origin = None

    def __repr__(self):
        return f"<WebpackMain Node: {self.value!r}>"

    def render(self, context):
        if self.name not in context and self.value:
            # set name in block parent context
            context.dicts[-2]["use_js_bundler"] = True
            context.dicts[-2][self.name] = self.value

        return ""


@register.tag
def js_entry(parser, token):
    """
    Indicate that a page should be using Webpack, by naming the
    JavaScript module to be used as the page's main entry point.

    The base template need not specify a value in its `{% js_entry %}`
    tag, allowing it to be extended by templates that may or may not
    use webpack. In this case the `js_entry` template variable
    will have a value of `None` unless an extending template has a
    `{% js_entry "..." %}` with a value.
    """
    return _bundler_main(parser, token, "__saw_js_entry", WebpackMainNode)
