import unittest

from camera.config import sanitize_capture_label
from camera.errors import CameraConfigError


class CameraConfigTests(unittest.TestCase):
    def test_sanitize_capture_label_allows_safe_names(self):
        self.assertEqual(sanitize_capture_label("desk test"), "desk_test")
        self.assertEqual(sanitize_capture_label("desk-01"), "desk-01")
        self.assertEqual(sanitize_capture_label(None), None)
        self.assertEqual(sanitize_capture_label("   "), None)

    def test_sanitize_capture_label_rejects_paths_and_long_labels(self):
        unsafe = ["../x", "/tmp/x", "desk/test", "x" * 49, ".hidden", "raw_pixels"]

        for label in unsafe:
            with self.subTest(label=label):
                with self.assertRaises(CameraConfigError):
                    sanitize_capture_label(label)


if __name__ == "__main__":
    unittest.main()
