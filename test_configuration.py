import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from configuration import load_config, clean_host

class CameraConfigurationTests(unittest.TestCase):
    def test_fresh_clone_has_no_network_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            config=load_config(Path(directory)/'missing.json')
            self.assertEqual((config.camera_host,config.blink_host,config.home_assistant_host),('','',''))
    def test_explicit_private_configuration_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'
            path.write_text(json.dumps({'camera_host':'192.0.2.10','blink_host':'camera.example','home_assistant_host':'home.example','home_assistant_port':8123}))
            config=load_config(path)
            self.assertEqual(config.camera_host,'192.0.2.10')
            self.assertTrue(config.viewer_helper.is_absolute())
    def test_host_is_not_a_url_or_command_argument(self):
        for host in ['-c','host;touch /tmp/no','http://user:password@example.com','example.com/path','999.0.0.1','example..com','-host.example',22]:
            with self.subTest(host=host),self.assertRaises(ValueError):clean_host(host)
    def test_invalid_config_is_rejected(self):
        for data in [{'home_assistant_port':True},{'home_assistant_port':0},{'home_assistant_port':65536},{'viewer_helper':'relative/script'},{'password':'not-a-config-field'},[]]:
            with self.subTest(data=data),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'config.json';path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):load_config(path)
    def test_environment_can_select_another_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json';path.write_text('{"camera_host":"camera.example"}')
            with patch.dict('os.environ',FOXTAIL_CAMERAS_CONFIG=str(path)):
                self.assertEqual(load_config().camera_host,'camera.example')

if __name__=='__main__':unittest.main()
