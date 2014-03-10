from django.utils.functional import memoize
from django.db.models import get_model as dj_get_model


def _get_class(module_label, classname):
    mod = None

    # try to import from the custom app
    try:
        mod = __import__('pybb.%s' % module_label, fromlist=[classname])
    except ImportError:
        pass  # continue searching

    if not mod or not hasattr(mod, classname):
        mod = __import__('pybb_core.pybb.%s' % module_label,
                         fromlist=[classname])

    return getattr(mod, classname)


get_class = memoize(_get_class, {}, 2)


def get_classes(module_label, classnames):
    for classname in classnames:
        yield get_class(module_label, classname)


def get_model(classname):
    return dj_get_model('pybb', classname)


def get_models(classnames):
    return [get_model(classname) for classname in classnames]
