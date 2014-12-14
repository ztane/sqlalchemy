class TOCMixin(object):
    def get_current_subtoc(self, current_page_name):
        """Return an integrated table of contents for the current page.

        This yields a hierarchy of TOC items that are only local
        or sub-nested to the current page, in a structure whereby the
        items that are on the immediate page can be distinguished from
        those that are on sub-pages.

        """

        raw_tree = self.app.env.get_toc_for(
            current_page_name, self.app.builder)

        stack = [raw_tree]
        while stack:
            elem = stack.pop(0)

# !list(context['current_subtoc']())
# context['app'].env.get_toctree_for(current_page_name, context['app'].builder, False)
# context['app'].env.get_toc_for(current_page_name, context['app'].builder)

            iscurrent = elem.attributes.get('iscurrent', False)
            refuri = elem.attributes.get('refuri', None)
            if refuri is not None:
                name = elem.children[0].rawsource
                remainders = elem.children[1:]
                if iscurrent:
                    yield refuri, name
            else:
                remainders = elem.children

            stack.extend(remainders)
