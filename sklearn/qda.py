import warnings
from .discriminant_analysis import QuadraticDiscriminantAnalysis

warnings.warn("qda.QDA has been moved to "
              "discriminant_analysis.QuadraticDiscriminantAnalysis "
              "in 0.17 and will be removed in 0.19.", DeprecationWarning)


class QDA(QuadraticDiscriminantAnalysis):
    """
    Alias for
    :class:`sklearn.discriminant_analysis.QuadraticDiscriminantAnalysis`.

    .. deprecated:: 0.17
        Deprecated :class:`sklearn.qda.QDA` will be removed in 0.19.
        Use
        :class:`sklearn.discriminant_analysis.QuadraticDiscriminantAnalysis`
        instead.
    """
    pass
