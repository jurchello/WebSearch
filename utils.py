import importlib

def is_module_available(module_name, function_name=None):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"⚠ Please install the '{module_name}' library to enable more features.")
        return False

    try:
        module = importlib.import_module(module_name)
        if function_name:
            return hasattr(module, function_name)
        return True
    except ImportError:
        print(f"⚠ Error importing '{module_name}'. Try reinstalling it.")
        return False