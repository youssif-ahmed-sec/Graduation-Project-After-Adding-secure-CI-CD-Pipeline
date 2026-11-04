
import unittest

from server.pdf_renderer import (
    DenyExternalResources,
    render_pdf,
)


class TestPDFRenderer(unittest.TestCase):

    def test_external_resources_are_blocked(self):
        fetcher = DenyExternalResources()

        blocked_urls = [
            "https://example.com/image.png",
            "http://127.0.0.1/private",
            "file:///C:/Windows/win.ini",
        ]

        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    fetcher.fetch(url)

    def test_pdf_generation(self):
        html = """
        <html>
        <body>
            <h1>FileTrack Test Report</h1>
            <p>No real evidence used.</p>
        </body>
        </html>
        """

        pdf = render_pdf(html)

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 1000)

    def test_embedded_png_is_allowed(self):
        import base64
        import io
        from PIL import Image

        image_buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(
            image_buffer,
            format="PNG",
        )

        image_bytes = image_buffer.getvalue()
        encoded = base64.b64encode(image_bytes).decode("ascii")

        fetcher = DenyExternalResources()
        result = fetcher.fetch(
            f"data:image/png;base64,{encoded}"
        )

        self.assertEqual(result.content_type, "image/png")
        self.assertEqual(result.read(), image_bytes)
        result.close()

        html = f"""
        <html>
        <body>
            <h1>Embedded Evidence Test</h1>
            <img src="data:image/png;base64,{encoded}">
        </body>
        </html>
        """

        pdf = render_pdf(html)

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 1000)

    def test_invalid_embedded_image_is_rejected(self):
        fetcher = DenyExternalResources()

        with self.assertRaises(ValueError):
            fetcher.fetch("data:image/png;base64,not-valid-base64!")


if __name__ == "__main__":
    unittest.main()
