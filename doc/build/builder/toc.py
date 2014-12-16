class TOCMixin(object):
    def get_current_subtoc(self, current_page_name, current_page_title):
        """Return a TOC for sub-files of the current file.

        """

        raw_tree = self.app.env.get_toctree_for(
            current_page_name, self.app.builder, True, maxdepth=0)
        local_tree = self.app.env.get_toc_for(
            current_page_name, self.app.builder)


        def _locate_nodes(nodes, level, outer=True):
            for elem in nodes:

                if hasattr(elem, 'attributes'):
                    refuri = elem.attributes.get('refuri', None)
                else:
                    refuri = None

                name = None
                if refuri is not None:
                    name = elem.children[0].rawsource
                    remainders = elem.children[1:]

                    # not really sure what get_toc_for() does, seems
                    # to keep returning nodes past what is local,
                    # so just do a brute force filter here
                    if (
                        not outer and refuri.startswith("#")
                    ) or (
                        outer and "#" not in refuri
                    ):
                        yield level, refuri, name
                else:
                    remainders = elem.children

                # try to embed the item-level get_toc_for() inside
                # the file-level get_toctree_for(), otherwise if we
                # just get the full get_toctree_for(), it's enormous,
                # why bother.
                if outer and name == current_page_title:
                    for ent in _locate_nodes([local_tree], level + 1, False):
                        yield ent
                else:
                    for ent in _locate_nodes(
                        remainders, level + 1, outer):
                        yield ent

        def _organize_nodes(nodes):
            stack = []
            levels = []
            for level, refuri, name in nodes:
                if not levels or levels[-1] < level:
                    levels.append(level)
                    new_collection = []
                    if stack:
                        stack[-1].append(new_collection)
                    stack.append(new_collection)
                elif level < levels[-1]:
                    while levels and level < levels[-1]:
                        stack.pop(-1)
                        levels.pop(-1)

                stack[-1].append((refuri, name))
            return stack

        def _render_nodes(stack, searchfor, level=0, nested_element=False):
            if stack:
                indent = " " * level
                printing = nested_element or searchfor in stack
                if printing:
                    yield (" " * level) + "<ul>"
                while stack:
                    elem = stack.pop(0)
                    as_links = searchfor != elem
                    if isinstance(elem, tuple):
                        if not stack or isinstance(stack[0], tuple):
                            if printing:
                                if as_links:
                                    yield "%s<li><a href='%s'>%s</a></li>" % ((indent,) + elem)
                                else:
                                    yield "%s<li><strong>%s</strong></li>" % (indent, elem[1])
                        elif isinstance(stack[0], list):
                            if printing:
                                if as_links:
                                    yield "%s<li><a href='%s'>%s</a>" % ((indent,) + elem)
                                else:
                                    yield "%s<li><strong>%s</strong>" % (indent, elem[1])
                            for sub in _render_nodes(
                                    stack[0], searchfor,
                                    level=level + 1,
                                    nested_element=nested_element or
                                    searchfor == elem):
                                yield sub
                            if printing:
                                yield (" " * level) + "</li>"
                    elif isinstance(elem, list):
                        for sub in _render_nodes(
                                elem, searchfor,
                                level=level + 1, nested_element=nested_element):
                            yield sub
                if printing:
                    yield (" " * level) + "</ul>"

        return "\n".join(
            _render_nodes(
                _organize_nodes(_locate_nodes([raw_tree], 0)),
                ('', current_page_title)
            )
        )
