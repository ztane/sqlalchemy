class TOCMixin(object):
    def get_current_subtoc(self, current_page_name):
        """Return a TOC for sub-files of the current file.

        """

        raw_tree = self.app.env.get_toc_for(
            current_page_name, self.app.builder)

        def _yield_nodes(nodes):
            for elem in nodes:

                if hasattr(elem, 'attributes'):
                    refuri = elem.attributes.get('refuri', None)
                    entries = elem.attributes.get('entries', None)
                else:
                    refuri = None
                    entries = None

                if refuri:
                    yield "<ul>"
                    name = elem.children[0].rawsource
                    remainders = elem.children[1:]
                    yield "<li><a href='%s'>%s</a></li>"% (
                            refuri, name
                        )
                else:
                    remainders = elem.children

                for ent in _yield_nodes(remainders):
                    yield ent
                if entries:
                    yield "<ul>"
                    for ent in entries:
                        yield "<li><a href='%s'>%s</a></li>" % (
                            ent[1], self._title_for_file(ent[1]))
                    yield "</ul>"

                if refuri:
                    yield "</ul>"

        return "\n".join(_yield_nodes([raw_tree]))


    def _title_for_file(self, file_):
        try:
            node = self.app.env.titles[file_]
        except KeyError:
            return None
        else:
            return node.children[0].rawsource