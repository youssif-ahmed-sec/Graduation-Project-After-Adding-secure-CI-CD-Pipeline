
import base64
import binascii
import io

from weasyprint import HTML
from weasyprint.urls import URLFetcher, URLFetcherResponse

class DenyExternalResources(URLFetcher):
    MAX_IMAGE_BYTES = 5 * 1024 * 1024

    def __init__(self):
        super().__init__(fail_on_errors=False)

    def fetch(self, url, headers=None):
        allowed_types = {
            "data:image/png;base64,": "image/png",
            "data:image/jpeg;base64,": "image/jpeg",
        }

        prefix, separator, encoded = url.partition(",")

        mime_type = allowed_types.get(prefix.lower() + separator)

        if mime_type is None:
            raise ValueError("External PDF resources are disabled")

        # Base64 expands binary data by approximately 4/3.
        if len(encoded) > ((self.MAX_IMAGE_BYTES + 2) // 3) * 4:
            raise ValueError("Embedded image exceeds size limit")

        try:
            image_bytes = base64.b64decode(
                encoded,
                validate=True,
            )
        except (binascii.Error, ValueError):
            raise ValueError("Invalid embedded image encoding")

        if len(image_bytes) > self.MAX_IMAGE_BYTES:
            raise ValueError("Embedded image exceeds size limit")

        return URLFetcherResponse(
            url=url,
            body=image_bytes,
            headers={"Content-Type": mime_type},
        )


def render_pdf(html_content):
    """
    Render HTML to PDF, allowing only embedded PNG/JPEG images.
    Network and local file access are disabled by the URL fetcher.
    """
    return HTML(
        string=html_content,
        url_fetcher=DenyExternalResources(),
    ).write_pdf()
