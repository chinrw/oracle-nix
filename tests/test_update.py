"""Exercise updater failure semantics without calling npm or Nix."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('update',Path(__file__).resolve().parents[1]/'scripts/update.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.package=self.root/'package'
        self.package.mkdir()
        manifest={'name':'oracle-nix','version':'0.23.0','private':True,'dependencies':{'@steipete/oracle':'0.23.0'}}
        lock={'version':'0.23.0','packages':{'node_modules/@steipete/oracle':{'version':'0.23.0','integrity':'sha512-fixture'}}}
        (self.package/'package.json').write_text(json.dumps(manifest))
        (self.package/'package-lock.json').write_text(json.dumps(lock))
        (self.package/'npm-deps-hash').write_text('sha256-'+'A'*43+'=\n')
        self.before=self.snapshot()

    def snapshot(self):
        return {p.name:p.read_bytes() for p in self.package.iterdir()}

    def resolve(self,args,cwd=None):
        if args[:2]==['npm','install']:
            lock=json.loads((cwd/'package-lock.json').read_text())
            lock['version']='0.24.0'
            lock['packages']['node_modules/@steipete/oracle']['version']='0.24.0'
            (cwd/'package-lock.json').write_text(json.dumps(lock))
            return ''
        return 'sha256-'+'B'*43+'='

    def test_no_update_does_not_rewrite_files(self):
        with patch.object(update,'command',return_value='"0.23.0"') as run:
            result=update.update(self.root)
        self.assertFalse(result['changed'])
        self.assertEqual(run.call_count,1)
        self.assertEqual(self.snapshot(),self.before)

    def test_check_reports_new_version_without_mutation(self):
        with patch.object(update,'command',return_value='"0.24.0"'):
            result=update.update(self.root,check=True)
        self.assertTrue(result['update_available'])
        self.assertFalse(result['changed'])
        self.assertEqual(self.snapshot(),self.before)

    def test_metadata_error_is_not_no_update(self):
        with patch.object(update,'command',side_effect=subprocess.CalledProcessError(1,['npm'])):
            with self.assertRaises(subprocess.CalledProcessError):
                update.update(self.root)
        self.assertEqual(self.snapshot(),self.before)

    def test_failed_hash_preserves_all_files(self):
        def fail(args,cwd=None):
            if args[0]=='prefetch-npm-deps':
                raise subprocess.CalledProcessError(1,args)
            return self.resolve(args,cwd)
        with patch.object(update,'command',side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                update.update(self.root,target='0.24.0')
        self.assertEqual(self.snapshot(),self.before)

    def test_success_updates_manifest_lock_and_hash(self):
        with patch.object(update,'command',side_effect=self.resolve):
            result=update.update(self.root,target='0.24.0')
        self.assertTrue(result['changed'])
        manifest=json.loads((self.package/'package.json').read_text())
        lock=json.loads((self.package/'package-lock.json').read_text())
        self.assertEqual(manifest['version'],'0.24.0')
        self.assertEqual(manifest['dependencies']['@steipete/oracle'],'0.24.0')
        self.assertEqual(lock['packages']['node_modules/@steipete/oracle']['version'],'0.24.0')
        self.assertEqual((self.package/'npm-deps-hash').read_text(),'sha256-'+'B'*43+'=\n')

    def test_invalid_release_rejected_before_resolution(self):
        for version in ('latest','0.24.0-beta.1','0.24.0; echo nope'):
            with self.subTest(version=version), patch.object(update,'command') as run:
                with self.assertRaises(ValueError):
                    update.update(self.root,target=version)
                run.assert_not_called()


if __name__=='__main__':
    unittest.main()
