import aiohttp
import asyncio
import os
import unittest
from unittest import mock
from aiohttp import web
from aiohttp.web import UrlDispatcher
from aiohttp.helpers import FileSender
from tests.test_web_functional import StaticFileMixin


class TestWebSendFile(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.router = UrlDispatcher()

    def tearDown(self):
        self.loop.close()

    # def make_handler(self):
    #     @asyncio.coroutine
    #     def handler(request):
    #         return aiohttp.Response(request)  # pragma: no cover
    #
    #     return handler

    def test_env_nosendfile(self):
        directory = os.path.dirname(__file__)

        with mock.patch.dict(os.environ, {'AIOHTTP_NOSENDFILE': '1'}):
            route = web.StaticRoute(None, "/", directory)
            file_sender = FileSender(resp_factory=route._response_factory,
                                     chunk_size=route._chunk_size
                                     )
            self.assertEqual(file_sender._sendfile,
                             file_sender._sendfile_fallback)

    def test_static_handle_eof(self):
        loop = mock.Mock()
        route = self.router.add_static('/st',
                                       os.path.dirname(aiohttp.__file__))
        with mock.patch('aiohttp.helpers.os') as m_os:
            out_fd = 30
            in_fd = 31
            fut = asyncio.Future(loop=self.loop)
            m_os.sendfile.return_value = 0
            file_sender = FileSender(resp_factory=route._response_factory,
                                     chunk_size=route._chunk_size
                                     )
            file_sender._sendfile_cb(fut, out_fd, in_fd, 0, 100, loop, False)
            m_os.sendfile.assert_called_with(out_fd, in_fd, 0, 100)
            self.assertTrue(fut.done())
            self.assertIsNone(fut.result())
            self.assertFalse(loop.add_writer.called)
            self.assertFalse(loop.remove_writer.called)

    def test_static_handle_again(self):
        loop = mock.Mock()
        route = self.router.add_static('/st',
                                       os.path.dirname(aiohttp.__file__))
        with mock.patch('aiohttp.helpers.os') as m_os:
            out_fd = 30
            in_fd = 31
            fut = asyncio.Future(loop=self.loop)
            m_os.sendfile.side_effect = BlockingIOError()
            file_sender = FileSender(resp_factory=route._response_factory,
                                     chunk_size=route._chunk_size
                                     )
            file_sender._sendfile_cb(fut, out_fd, in_fd, 0, 100, loop, False)
            m_os.sendfile.assert_called_with(out_fd, in_fd, 0, 100)
            self.assertFalse(fut.done())
            loop.add_writer.assert_called_with(out_fd,
                                               file_sender._sendfile_cb,
                                               fut, out_fd, in_fd, 0, 100,
                                               loop, True)
            self.assertFalse(loop.remove_writer.called)

    def test_static_handle_exception(self):
        loop = mock.Mock()
        route = self.router.add_static('/st',
                                       os.path.dirname(aiohttp.__file__))
        with mock.patch('aiohttp.helpers.os') as m_os:
            out_fd = 30
            in_fd = 31
            fut = asyncio.Future(loop=self.loop)
            exc = OSError()
            m_os.sendfile.side_effect = exc
            file_sender = FileSender(resp_factory=route._response_factory,
                                     chunk_size=route._chunk_size
                                     )
            file_sender._sendfile_cb(fut, out_fd, in_fd, 0, 100, loop, False)
            m_os.sendfile.assert_called_with(out_fd, in_fd, 0, 100)
            self.assertTrue(fut.done())
            self.assertIs(exc, fut.exception())
            self.assertFalse(loop.add_writer.called)
            self.assertFalse(loop.remove_writer.called)


class TestStaticFileSendfileFallback(StaticFileMixin,
                                     unittest.TestCase):
    def patch_sendfile(self, add_static):
        def f(*args, **kwargs):
            route = add_static(*args, **kwargs)
            from aiohttp.helpers import FileSender
            file_sender = FileSender(resp_factory=route._response_factory,
                                     chunk_size=route._chunk_size
                                     )
            file_sender._sendfile = file_sender._sendfile_fallback
            return route
        return f
