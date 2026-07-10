"""handler_base.py / registry.py 单元测试"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mmfb.core.handler_base import BaseHandler, MimeCache
from mmfb.core.registry import HandlerRegistry


class _PdfHandler(BaseHandler):
    extensions = [".pdf"]

    def get_preview(self):
        return {"mime": "application/pdf", "data": self.path}

    def get_edit(self):
        return {"mime": "text/plain", "data": "editable content"}


class _TxtHandler(BaseHandler):
    extensions = [".txt"]

    def get_preview(self):
        return {"mime": "text/plain", "data": self.path}


class _TarGzHandler(BaseHandler):
    extensions = [".tar.gz"]

    def get_preview(self):
        return {"mime": "application/gzip", "data": self.path}


class _MultiExtHandler(BaseHandler):
    extensions = [".jpg", ".jpeg", ".png"]

    def get_preview(self):
        return {"mime": "image/*", "data": self.path}


class _EmptyExtHandler(BaseHandler):
    extensions = []

    def get_preview(self):
        return None


class TestMimeCache(unittest.TestCase):

    def setUp(self):
        MimeCache.clear()

    def test_known_extension(self):
        self.assertEqual(MimeCache.get_mime("doc.pdf"), "application/pdf")

    def test_text_extension(self):
        self.assertEqual(MimeCache.get_mime("file.txt"), "text/plain")

    def test_unknown_extension_returns_default(self):
        self.assertEqual(
            MimeCache.get_mime("file.xyzzy"), "application/octet-stream"
        )

    def test_caching(self):
        MimeCache.get_mime("a.pdf")
        MimeCache.get_mime("b.pdf")
        MimeCache.get_mime("c.pdf")
        info = MimeCache.get_mime.cache_info()
        self.assertEqual(info.currsize, 3)

    def test_clear(self):
        MimeCache.get_mime("test.pdf")
        self.assertGreater(MimeCache.get_mime.cache_info().currsize, 0)
        MimeCache.clear()
        self.assertEqual(MimeCache.get_mime.cache_info().currsize, 0)


class TestBaseHandler(unittest.TestCase):

    def test_can_handle_matching_suffix(self):
        self.assertTrue(_PdfHandler.can_handle("document.pdf"))
        self.assertTrue(_PdfHandler.can_handle("/path/to/file.pdf"))

    def test_can_handle_case_insensitive(self):
        self.assertTrue(_PdfHandler.can_handle("document.PDF"))
        self.assertTrue(_PdfHandler.can_handle("document.Pdf"))

    def test_can_handle_rejects_unrelated(self):
        self.assertFalse(_PdfHandler.can_handle("file.txt"))
        self.assertFalse(_PdfHandler.can_handle("noextension"))

    def test_can_handle_no_match_suffix(self):
        self.assertFalse(_PdfHandler.can_handle("file.pdfx"))

    def test_get_mime(self):
        handler = _PdfHandler("test.pdf")
        self.assertEqual(handler.get_mime(), "application/pdf")

    def test_get_edit_default_returns_none(self):
        handler = _TxtHandler("file.txt")
        self.assertIsNone(handler.get_edit())

    def test_get_edit_when_overridden(self):
        handler = _PdfHandler("doc.pdf")
        edit = handler.get_edit()
        self.assertIsNotNone(edit)
        self.assertIn("mime", edit)

    def test_supports_editing_false(self):
        handler = _TxtHandler("file.txt")
        self.assertFalse(handler.supports_editing())

    def test_supports_editing_true(self):
        handler = _PdfHandler("doc.pdf")
        self.assertTrue(handler.supports_editing())

    def test_abstract_instantiation_raises(self):
        with self.assertRaises(TypeError):
            BaseHandler("test.txt")

    def test_path_stored(self):
        handler = _TxtHandler("/foo/bar.txt")
        self.assertEqual(handler.path, "/foo/bar.txt")


class TestHandlerRegistry(unittest.TestCase):

    def setUp(self):
        self.reg = HandlerRegistry()

    def test_register_and_get_simple(self):
        self.reg.register(".pdf", _PdfHandler)
        handler = self.reg.get_handler("doc.pdf")
        self.assertIsInstance(handler, _PdfHandler)
        self.assertEqual(handler.path, "doc.pdf")

    def test_register_and_get_compound(self):
        self.reg.register(".tar.gz", _TarGzHandler)
        handler = self.reg.get_handler("archive.tar.gz")
        self.assertIsInstance(handler, _TarGzHandler)

    def test_compound_takes_priority(self):
        self.reg.register(".gz", _TxtHandler)
        self.reg.register(".tar.gz", _TarGzHandler)
        handler = self.reg.get_handler("archive.tar.gz")
        self.assertIsInstance(handler, _TarGzHandler)

    def test_simple_suffix_fallback(self):
        self.reg.register(".gz", _TxtHandler)
        handler = self.reg.get_handler("file.gz")
        self.assertIsInstance(handler, _TxtHandler)

    def test_get_handler_returns_none_when_unregistered(self):
        handler = self.reg.get_handler("unknown.xyz")
        self.assertIsNone(handler)

    def test_case_insensitive_lookup(self):
        self.reg.register(".pdf", _PdfHandler)
        handler = self.reg.get_handler("MyDocument.PDF")
        self.assertIsInstance(handler, _PdfHandler)

    def test_register_class(self):
        self.reg.register_class(_MultiExtHandler)
        self.assertIsInstance(self.reg.get_handler("photo.jpg"), _MultiExtHandler)
        self.assertIsInstance(self.reg.get_handler("photo.jpeg"), _MultiExtHandler)
        self.assertIsInstance(self.reg.get_handler("photo.png"), _MultiExtHandler)

    def test_register_class_empty_extensions(self):
        self.reg.register_class(_EmptyExtHandler)
        self.assertEqual(self.reg.count(), 0)

    def test_invalid_extension_raises(self):
        with self.assertRaises(ValueError):
            self.reg.register("", _PdfHandler)
        with self.assertRaises(ValueError):
            self.reg.register("pdf", _PdfHandler)
        with self.assertRaises(ValueError):
            self.reg.register("nodot", _PdfHandler)

    def test_non_handler_class_raises(self):
        with self.assertRaises(TypeError):
            self.reg.register(".foo", object)
        with self.assertRaises(TypeError):
            self.reg.register(".foo", dict)

    def test_unregister_existing(self):
        self.reg.register(".pdf", _PdfHandler)
        self.assertTrue(self.reg.unregister(".pdf"))
        self.assertIsNone(self.reg.get_handler("doc.pdf"))

    def test_unregister_nonexistent(self):
        self.assertFalse(self.reg.unregister(".xyz"))

    def test_unregister_case_insensitive(self):
        self.reg.register(".pdf", _PdfHandler)
        self.assertTrue(self.reg.unregister(".PDF"))
        self.assertEqual(self.reg.count(), 0)

    def test_list_extensions(self):
        self.reg.register(".pdf", _PdfHandler)
        self.reg.register(".txt", _TxtHandler)
        self.reg.register(".tar.gz", _TarGzHandler)
        exts = self.reg.list_extensions()
        self.assertEqual(exts, [".pdf", ".tar.gz", ".txt"])

    def test_list_handlers(self):
        self.reg.register(".pdf", _PdfHandler)
        handlers = self.reg.list_handlers()
        self.assertIn((".pdf", "_PdfHandler"), handlers)

    def test_count(self):
        self.assertEqual(self.reg.count(), 0)
        self.reg.register(".pdf", _PdfHandler)
        self.assertEqual(self.reg.count(), 1)
        self.reg.register(".txt", _TxtHandler)
        self.assertEqual(self.reg.count(), 2)

    def test_path_with_dots_in_dir(self):
        self.reg.register(".pdf", _PdfHandler)
        handler = self.reg.get_handler("/home/user.name/doc.pdf")
        self.assertIsInstance(handler, _PdfHandler)

    def test_overwrite_registration(self):
        self.reg.register(".pdf", _PdfHandler)
        self.reg.register(".pdf", _TxtHandler)
        handler = self.reg.get_handler("doc.pdf")
        self.assertIsInstance(handler, _PdfHandler)
        self.assertEqual(self.reg.count(), 1)


class TestHandlerRegistryIntegration(unittest.TestCase):

    def setUp(self):
        self.reg = HandlerRegistry()
        self.reg.register_class(_PdfHandler)
        self.reg.register_class(_TxtHandler)
        self.reg.register_class(_MultiExtHandler)

    def test_dispatch_pdf(self):
        handler = self.reg.get_handler("report.pdf")
        self.assertIsInstance(handler, _PdfHandler)

    def test_dispatch_txt(self):
        handler = self.reg.get_handler("notes.txt")
        self.assertIsInstance(handler, _TxtHandler)

    def test_dispatch_multi_ext_first_match(self):
        handler = self.reg.get_handler("photo.jpg")
        self.assertIsInstance(handler, _MultiExtHandler)

    def test_dispatch_case_insensitive(self):
        handler = self.reg.get_handler("report.PDF")
        self.assertIsInstance(handler, _PdfHandler)

    def test_dispatch_returns_none_for_unknown(self):
        handler = self.reg.get_handler("data.unknown")
        self.assertIsNone(handler)

    def test_dispatch_full_path(self):
        handler = self.reg.get_handler("/home/user/docs/report.pdf")
        self.assertIsInstance(handler, _PdfHandler)

    def test_handler_instantiated_with_full_path(self):
        handler = self.reg.get_handler("/tmp/test.pdf")
        self.assertEqual(handler.path, "/tmp/test.pdf")

    def test_handler_preview_output(self):
        handler = self.reg.get_handler("doc.pdf")
        preview = handler.get_preview()
        self.assertEqual(preview["mime"], "application/pdf")

    def test_handler_edit_output(self):
        handler = self.reg.get_handler("doc.pdf")
        edit = handler.get_edit()
        self.assertIsNotNone(edit)
        self.assertIn("mime", edit)
