from django.utils.functional import memoize
from django.db.models import get_app, get_model as dj_get_model


def _pybb_import(module_label, objname):
    try:
        app = get_app('pybb').__package__
        mod = __import__('%s.%s' % (app, module_label), fromlist=[objname])
    except ImportError:
        mod = None  # continue searching

    if not mod or (objname != '*' and not hasattr(mod, objname)):
        mod = __import__('pybb_core.pybb.%s' % module_label,
                         fromlist=[objname])

    return mod


_pybb_import_wrapper = memoize(_pybb_import, {}, 2)


def pybb_import(module_label, objname=None):
    return _pybb_import_wrapper(module_label, objname or '*')


def get_class(module_label, classname):
    return getattr(pybb_import(module_label, classname), classname)


def get_classes(module_label, classnames):
    for classname in classnames:
        yield get_class(module_label, classname)


def get_model(classname):
    return dj_get_model('pybb', classname)


def get_models(classnames):
    return [get_model(classname) for classname in classnames]
