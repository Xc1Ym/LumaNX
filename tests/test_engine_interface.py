"""The Worker calls the bundled engine with the arguments the engine declares."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'Engine/nxnative/scripts/build_ipa_from_nsp.py'


def engine_api(path):
    """The engine's top level names and the parameters of its functions."""
    names = set()
    functions = {}
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            args = node.args
            positional = [a.arg for a in args.posonlyargs + args.args]
            defaults = len(args.defaults)
            functions[node.name] = {
                'positional': positional,
                'required': positional[:len(positional) - defaults],
                'kwonly': [a.arg for a in args.kwonlyargs],
                'kwonly_required': [a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is None],
                'vararg': args.vararg is not None,
                'kwargs': args.kwarg is not None,
            }
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split('.')[0])
    return names, functions


def mismatch(signature, args, keywords, splat):
    """Why the call does not fit the signature, or None when it does."""
    positional = signature['positional']
    if len(args) > len(positional) and not signature['vararg']:
        return f"{len(args)} positional arguments for {len(positional)} parameters"
    taken = positional[:len(args)]
    supplied = {}
    for keyword in keywords:
        if keyword.arg is None:
            continue
        if keyword.arg in taken:
            return f"multiple values for argument '{keyword.arg}'"
        if keyword.arg not in positional and keyword.arg not in signature['kwonly'] and not signature['kwargs']:
            return f"unexpected keyword argument '{keyword.arg}'"
        supplied[keyword.arg] = keyword
    if splat and len(taken) >= len(positional) and not signature['kwargs']:
        return 'the keyword splat would repeat a positional argument'
    missing = [p for p in signature['required'] if p not in taken and p not in supplied]
    missing += [p for p in signature['kwonly_required'] if p not in supplied]
    if missing:
        return 'missing argument(s): ' + ', '.join(missing)
    return None


class EngineInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names, cls.functions = engine_api(ENGINE)

    def calls(self):
        for path in sorted((ROOT / 'Worker').glob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            guarded = {node.args[1].value for node in ast.walk(tree)
                       if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id == 'hasattr' and len(node.args) == 2
                       and isinstance(node.args[0], ast.Name) and node.args[0].id == 'up'
                       and isinstance(node.args[1], ast.Constant)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'up':
                    yield path, node, guarded

    def test_every_call_fits_the_engine_signature(self):
        for path, node, _ in self.calls():
            name = node.func.attr
            if name not in self.functions:
                continue
            splat = any(keyword.arg is None for keyword in node.keywords)
            why = mismatch(self.functions[name], node.args, node.keywords, splat)
            self.assertIsNone(why, f'{path.name}:{node.lineno} up.{name}(): {why}')

    def test_every_engine_function_called_exists(self):
        for path, node, guarded in self.calls():
            name = node.func.attr
            if name in self.names:
                continue
            self.assertIn(name, guarded, f'{path.name}:{node.lineno} calls up.{name}(), which the engine does not have')


if __name__ == '__main__':
    unittest.main()
