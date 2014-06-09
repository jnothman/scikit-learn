import warnings
import numpy as np
import numpy.linalg as la
from scipy import sparse
from functools import partial

from scipy.stats.mstats import mquantiles

from sklearn.utils.testing import assert_almost_equal
from sklearn.utils.testing import assert_array_almost_equal
from sklearn.utils.testing import assert_array_equal
from sklearn.utils.testing import assert_equal
from sklearn.utils.testing import assert_raises
from sklearn.utils.testing import assert_true
from sklearn.utils.testing import assert_false
from sklearn.utils.testing import assert_warns

from sklearn.utils.sparsefuncs import mean_variance_axis
from sklearn.preprocessing.data import _transform_selected
from sklearn.preprocessing.data import Binarizer
from sklearn.preprocessing.data import KernelCenterer
from sklearn.preprocessing.data import Normalizer
from sklearn.preprocessing.data import normalize
from sklearn.preprocessing.data import OneHotEncoder
from sklearn.preprocessing.data import StandardScaler
from sklearn.preprocessing.data import scale
from sklearn.preprocessing.data import RobustScaler
from sklearn.preprocessing.data import robust_scale
from sklearn.preprocessing.data import MinMaxScaler
from sklearn.preprocessing.data import MaxAbsScaler
from sklearn.preprocessing.data import minmax_scale
from sklearn.preprocessing.data import maxabs_scale
from sklearn.preprocessing.data import add_dummy_feature
from sklearn.preprocessing.data import PolynomialFeatures

from sklearn import datasets


iris = datasets.load_iris()


SPARSE_SCALERS = {  # support sparse or dense input
    'uncentered StandardScaler': partial(StandardScaler, with_centering=False),
    'MaxAbsScaler': MaxAbsScaler
}

NON_SPARSE_SCALERS = {  # only support dense input
    'centered StandardScaler': partial(StandardScaler, with_centering=True),
    'MaxAbsScaler': MaxAbsScaler,
    'RobustScaler': RobustScaler,
    'MinMaxScaler[0,1]': partial(MinMaxScaler, feature_range=(0, 1)),
    'MinMaxScaler[-1,1]': partial(MinMaxScaler, feature_range=(-1, 1)),
    'MinMaxScaler[-3,5]': partial(MinMaxScaler, feature_range=(-3, 5))
}


ALL_SCALERS = {}
ALL_SCALERS.update(SPARSE_SCALERS)
ALL_SCALERS.update(NON_SPARSE_SCALERS)


SCALER_FUNCTIONS = {
    'scale': scale,
    'robust_scale': robust_scale,
    'minmax_scale': minmax_scale,
    'maxabs_scale': maxabs_scale
}

    interact = PolynomialFeatures(2, interaction_only=True, include_bias=True)
    X_poly = interact.fit_transform(X)
    assert_array_almost_equal(X_poly, P2[:, [0, 1, 2, 4]])


def test_scaler_2d_axis0():
    """Test robust scaling of 2d array along axis0"""
    rng = np.random.RandomState(0)
    X = rng.randn(4, 5)
    X[:, 0] = 0.0  # first feature is always of zero

    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass(axis=0)
        X_scaled = scaler.fit(X).transform(X, copy=True)
        assert_false(np.any(np.isnan(X_scaled)))

        assert_array_almost_equal(X_scaled.std(axis=0)[0], 0)
        # Check that X has been copied
        assert_true(X_scaled is not X)

        # check inverse transform
        X_scaled_back = scaler.inverse_transform(X_scaled)
        assert_true(X_scaled_back is not X)
        assert_true(X_scaled_back is not X_scaled)
        assert_array_almost_equal(X_scaled_back, X)

        assert_false(np.any(np.isnan(X_scaled)))
        # Check that the data hasn't been modified
        assert_true(X_scaled is not X)

        X_scaled = scaler.fit(X).transform(X, copy=False)
        # Check that X has not been copied
        assert_true(X_scaled is X)


def test_scaler_2d_axis1():
    '''Check that scalers work on 2D arrays on axis=1'''
    rng = np.random.RandomState(42)
    X = rng.randn(4, 5)
    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass().fit(X)
        scaler_trans = ScalerClass(axis=1).fit(X.T)
        X_scaled = scaler.transform(X)
        X_scaled_trans = scaler_trans.transform(X.T)
        assert_array_almost_equal(X_scaled.T, X_scaled_trans)
        X_inv = scaler.inverse_transform(X_scaled)
        X_trans_inv = scaler_trans.inverse_transform(X_scaled_trans)
        assert_array_almost_equal(X_inv.T, X_trans_inv)

    for fn, scale_func in SCALER_FUNCTIONS.items():
        X_scaled = scale_func(X)
        X_scaled_trans = scale_func(X.T, axis=1)
        assert_array_almost_equal(X_scaled.T, X_scaled_trans)


def test_scaler_1D():
    '''Check that scalers accept 1D input'''
    X = np.array([-1, 0.0, 1.6])
    Xl = [-1, 0.0, 1.6]  # 1D list
    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass()
        X_trans = scaler.fit_transform(X)
        X_inv = scaler.inverse_transform(X_trans)
        assert_array_almost_equal(X_inv, X)

        Xl_trans = scaler.fit_transform(Xl)
        assert_array_almost_equal(X_trans, Xl_trans)
        X_trans2 = np.squeeze(scaler.fit_transform(np.transpose([X])))
        assert_array_almost_equal(Xl_trans, X_trans2)
        X_inv = scaler.inverse_transform(Xl_trans)
        assert_array_almost_equal(X_inv, Xl)
        Xl_inv = scaler.inverse_transform(Xl_trans.tolist())
        assert_array_almost_equal(X_inv, Xl_inv)

    for fn, scale_func in SCALER_FUNCTIONS.items():
        scale_func(X)


def test_scale_axis1_allzeros():
    X = np.array([0.0, 0.0, 0.0, 0.0])
    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass().fit(X)
        X_scaled = scaler.transform(X)
        if "MinMaxScaler" in fn:
            continue
        assert_array_almost_equal(X_scaled, X)
        X_inv = scaler.inverse_transform(X_scaled)
        assert_array_almost_equal(X_inv, X)

    for fn, scale_func in SCALER_FUNCTIONS.items():
        X_scaled = scale_func(X)
        assert_array_almost_equal(X_scaled, X)


def test_scaler_sparse_data():
    """Check that the scalers works with sparse inputs."""
    X = [[0., 1., +0.5, -1],
         [0., 1., -0.3, -0.5],
         [0., 1., -1.5, 0],
         [0., 0., +0.0, -2]]

    X_csr = sparse.csr_matrix(X)
    X_csc = sparse.csc_matrix(X)

    for axis in (0, 1):
        for fn, ScalerClass in SPARSE_SCALERS.items():
            scaler = ScalerClass(axis=axis)
            scaler_csr = ScalerClass(axis=axis)
            scaler_csc = ScalerClass(axis=axis)
            X_trans = scaler.fit_transform(X)
            X_trans_csr = scaler_csr.fit_transform(X_csr)
            X_trans_csc = scaler_csc.fit_transform(X_csc)
            assert_false(np.any(np.isnan(X_trans_csr.data)))
            assert_false(np.any(np.isnan(X_trans_csc.data)))

            assert_array_almost_equal(X_trans, X_trans_csr.toarray())
            assert_array_almost_equal(X_trans, X_trans_csc.toarray())
            X_trans_inv = scaler.inverse_transform(X_trans)
            X_trans_inv_csr = scaler_csr.inverse_transform(X_trans_csr)
            X_trans_inv_csc = scaler_csc.inverse_transform(X_trans_csc)
            assert_false(np.any(np.isnan(X_trans_inv_csr.data)))
            assert_false(np.any(np.isnan(X_trans_inv_csc.data)))
            assert_array_almost_equal(X_trans_inv, X_trans_inv_csr.toarray())
            assert_array_almost_equal(X_trans_inv, X_trans_inv_csc.toarray())


def test_scaler_center_property():
    """Check that the center_ attribute of the Scalers is accessible"""
    X = [[0., 2.0, +0.5],
         [0., 0.0, -0.3]]
    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass()
        if not scaler.with_centering:
            continue
        scaler.fit_transform(X)
        assert(len(scaler.center_) == 3)

    scaler = StandardScaler().fit(X)
    with warnings.catch_warnings(record=True):
        assert(len(scaler.mean_) == 3)  # deprecated parameter


def test_scaler_scale_property():
    """Check that the scale_ attribute of Scalers is accessible"""
    X = [[0., 2.0, +0.5],
         [0., 0.0, -0.3]]

    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass()
        scaler.fit_transform(X)
        assert(len(scaler.scale_) == 3)

    scaler = StandardScaler().fit(X)
    with warnings.catch_warnings(record=True):
        assert(len(scaler.std_) == 3)  # deprecated parameter


def test_scaler_throw_exceptions_on_unallowed_sparse():
    """Check that the Scalers throw on unallowed matrix formats."""
    X = [[0., 2.0, +0.5],
         [0., 0.0, -0.3],
         [0., 4.0, -1.7]]
    X_dia = sparse.dia_matrix(X)

    for fn, ScalerClass in ALL_SCALERS.items():
        scaler = ScalerClass()
        assert_raises(TypeError, scaler.fit, X_dia)
        scaler.fit(X)
        did_raise = False
        try:
            scaler.transform(X_dia)
        except TypeError:
            did_raise = True
        assert(did_raise)


def test_scaler_matrix_copy_argument():
    '''Make sure the scalers respect the 'copy' argument on inputs.'''
    rng = np.random.RandomState(42)
    for fn, ScalerClass in ALL_SCALERS.items():
        X = rng.randn(4, 5)
        scaler = ScalerClass(copy=True).fit(X)
        X_scaled = scaler.transform(X)
        assert (X_scaled is not X)
        X2 = scaler.inverse_transform(X_scaled)
        assert (X_scaled is not X2)

        scaler = ScalerClass(copy=False).fit(X)
        X_scaled = scaler.transform(X)
        assert (X_scaled is X)
        X2 = scaler.inverse_transform(X_scaled)
        assert (X_scaled is X2)

        scaler = ScalerClass(copy=False).fit(X)
        X_scaled = scaler.transform(X, copy=True)
        assert (X_scaled is not X)
        X2 = scaler.inverse_transform(X_scaled, copy=True)
        assert (X_scaled is not X2)

        scaler = ScalerClass(copy=False).fit(X)
        X_scaled = scaler.transform(X)
        assert (X_scaled is X)


def test_scaler_sparse_matrix_copy_argument():
    '''Make sure the scalers respect the 'copy' argument on sparse inputs.'''
    rng = np.random.RandomState(42)
    for fn, ScalerClass in SPARSE_SCALERS.items():
        X = rng.randn(4, 5)
        X[0, 0] = 0
        X_csr = sparse.csr_matrix(X)

        scaler = ScalerClass(copy=True).fit(X_csr)
        X_scaled = scaler.transform(X_csr)
        assert (X_scaled is not X_csr)
        X2 = scaler.inverse_transform(X_scaled)
        assert (X_scaled is not X2)

        scaler = ScalerClass(copy=False).fit(X_csr)
        X_scaled = scaler.transform(X_csr)
        assert (X_scaled is X_csr)
        X2 = scaler.inverse_transform(X_scaled)
        assert (X_scaled is X2)

        scaler = ScalerClass(copy=False).fit(X_csr)
        X_scaled = scaler.transform(X_csr, copy=True)
        assert (X_scaled is not X_csr)
        X2 = scaler.inverse_transform(X_scaled, copy=True)
        assert (X_scaled is not X2)

        scaler = ScalerClass(copy=False).fit(X_csr)
        X_scaled = scaler.transform(X_csr)
        assert (X_scaled is X_csr)


def test_scaler_int():
    '''Test that scaler converts integer input to float'''
    rng = np.random.RandomState(42)
    X = rng.randint(20, size=(4, 5))
    X[:, 0] = 0  # first feature is always of zero
    X_csr = sparse.csr_matrix(X)
    X_csc = sparse.csc_matrix(X)

    for fn, ScalerClass in ALL_SCALERS.items():
        try:
            null_transform = ScalerClass(with_centering=False,
                                         with_scaling=False, copy=True)
            with warnings.catch_warnings(record=True):
                X_null = null_transform.fit_transform(X)
            assert_array_equal(X_null, X)
        except TypeError:
            pass  # some classes can't be initialized with above args

        with warnings.catch_warnings(record=True):
            scaler = ScalerClass().fit(X)
            X_scaled = scaler.transform(X, copy=True)
        assert_false(np.any(np.isnan(X_scaled)))

         # Check that X has not been modified (copy)
        assert_true(X_scaled is not X)
        X_scaled_back = scaler.inverse_transform(X_scaled)
        assert_true(X_scaled_back is not X)
        assert_true(X_scaled_back is not X_scaled)
        assert_array_almost_equal(X_scaled_back, X)

    for fn, ScalerClass in SPARSE_SCALERS.items():
        with warnings.catch_warnings(record=True):
            scaler_csr = ScalerClass().fit(X_csr)
            X_csr_scaled = scaler_csr.transform(X_csr, copy=True)
        assert_false(np.any(np.isnan(X_csr_scaled.data)))

        with warnings.catch_warnings(record=True):
            scaler_csc = ScalerClass().fit(X_csc)
            X_csc_scaled = scaler_csc.transform(X_csc, copy=True)
        assert_false(np.any(np.isnan(X_csc_scaled.data)))

        X_csr_scaled_back = scaler_csr.inverse_transform(X_csr_scaled)
        assert_true(X_csr_scaled_back is not X_csr)
        assert_true(X_csr_scaled_back is not X_csr_scaled)
        assert_array_almost_equal(X_csr_scaled_back.toarray(), X)

        X_csc_scaled_back = scaler_csc.inverse_transform(X_csc_scaled.tocsc())
        assert_true(X_csc_scaled_back is not X_csc)
        assert_true(X_csc_scaled_back is not X_csc_scaled)
        assert_array_almost_equal(X_csc_scaled_back.toarray(), X)


def test_warning_scaling_integers():
    """Check warning when scaling integer data"""
    X = np.array([[1, 2, 0],
                  [0, 0, 0]], dtype=np.uint8)

    for fn, ScalerClass in ALL_SCALERS.items():
        assert_warns(UserWarning, ScalerClass().fit, X)


def test_nonsparse_scaler_raise_exception_on_sparse():
    rng = np.random.RandomState(42)
    X = rng.randn(4, 5)
    X_csr = sparse.csr_matrix(X)

    nonsparse = set(ALL_SCALERS.keys()) - set(SPARSE_SCALERS.keys())
    for fn in nonsparse:
        scaler = ALL_SCALERS[fn]()

        # some scalers don't except sparse matrices at all and will throw
        # a TypeError, while others except them only under certain conditions
        # and will throw a ValueError if that happens. Thus we test for
        # BaseException
        assert_raises(BaseException, scaler.fit, X_csr)
        scaler.fit(X)
        assert_raises(BaseException, scaler.transform, X_csr)
        X_transformed_csr = sparse.csr_matrix(scaler.transform(X))
        assert_raises(BaseException, scaler.inverse_transform,
                      X_transformed_csr)


def test_standardscaler_2d_arrays():
    """Test scaling of 2d array along first axis"""
    rng = np.random.RandomState(0)
    X = rng.randn(4, 5)
    X[:, 0] = 0.0  # first feature is always of zero

    scaler = StandardScaler()
    X_scaled = scaler.fit(X).transform(X, copy=True)

    assert_array_almost_equal(X_scaled.mean(axis=0), 5 * [0.0])
    assert_array_almost_equal(X_scaled.std(axis=0), [0., 1., 1., 1., 1.])

    X_scaled = scale(X, axis=1, with_scaling=False)
    assert_array_almost_equal(X_scaled.mean(axis=1), 4 * [0.0])
    X_scaled = scale(X, axis=1, with_scaling=True)
    assert_array_almost_equal(X_scaled.mean(axis=1), 4 * [0.0])
    assert_array_almost_equal(X_scaled.std(axis=1), 4 * [1.0])


def test_standard_scaler_zero_variance_features():
    """Check standard scaler on toy data with zero variance features"""
    X = [[0., 1., +0.5],
         [0., 1., -0.1],
         [0., 1., +1.1]]
    scaler = StandardScaler()
    X_trans = scaler.fit_transform(X)
    X_expected = [[0., 0.,  0.],
                  [0., 0., -1.22474487],
                  [0., 0.,  1.22474487]]
    assert_array_almost_equal(X_trans, X_expected)
    X_trans_inv = scaler.inverse_transform(X_trans)
    assert_array_almost_equal(X, X_trans_inv, decimal=4)

    X_new = [[+0., 2., 0.5],
             [-1., 1., 0.0],
             [+0., 1., 1.5]]
    X_trans_new = scaler.transform(X_new)
    X_expected_new = [[+0., 1.,  0.],
                      [-1., 0., -1.02062073],
                      [+0., 0.,  2.04124145]]
    assert_array_almost_equal(X_trans_new, X_expected_new, decimal=4)


def test_min_max_scaler_iris():
    X = iris.data
    scaler = MinMaxScaler()
    # default params
    X_trans = scaler.fit_transform(X)
    assert_array_almost_equal(X_trans.min(axis=0), 0)
    assert_array_almost_equal(X_trans.min(axis=0), 0)
    assert_array_almost_equal(X_trans.max(axis=0), 1)

    # not default params: min=1, max=2
    scaler = MinMaxScaler(feature_range=(1, 2))
    X_trans = scaler.fit_transform(X)
    assert_array_almost_equal(X_trans.min(axis=0), 1)
    assert_array_almost_equal(X_trans.max(axis=0), 2)

    # min=-.5, max=.6
    scaler = MinMaxScaler(feature_range=(-.5, .6))
    X_trans = scaler.fit_transform(X)
    assert_array_almost_equal(X_trans.min(axis=0), -.5)
    assert_array_almost_equal(X_trans.max(axis=0), .6)

    # minmax_scale function
    X_trans = minmax_scale(X)
    assert_array_almost_equal(X_trans.min(axis=0), 0)
    assert_array_almost_equal(X_trans.min(axis=0), 0)
    assert_array_almost_equal(X_trans.max(axis=0), 1)
    X_trans = minmax_scale(X, feature_range=(1, 2))
    assert_array_almost_equal(X_trans.min(axis=0), 1)
    assert_array_almost_equal(X_trans.max(axis=0), 2)
    X_trans = minmax_scale(X, feature_range=(-0.5, 0.6))
    assert_array_almost_equal(X_trans.min(axis=0), -0.5)
    assert_array_almost_equal(X_trans.max(axis=0),  0.6)


def test_min_max_scaler_raise_invalid_range():
    '''Check if MinMaxScaler raises an error if range is invalid'''
    X = [[0., 1., +0.5],
         [0., 1., -0.1],
         [0., 1., +1.1]]
    scaler = MinMaxScaler(feature_range=(2, 1))
    assert_raises(ValueError, scaler.fit, X)
    # TODO: for some reason assert_raise doesn't test this correctly
    did_raise = False
    try:
        minmax_scale(X, feature_range=(2, 1))
    except ValueError:
        did_raise = True
    assert_true(did_raise)


def test_min_max_scaler_zero_variance_features():
    """Check MinMaxScaler on toy data with zero variance features"""
    X = [[0., 1., +0.5],
         [0., 1., -0.1],
         [0., 1., +1.1]]

    X_new = [[+0., 2., 0.5],
             [-1., 1., 0.0],
             [+0., 1., 1.5]]

    # default params
    scaler = MinMaxScaler()
    X_trans = scaler.fit_transform(X)
    X_expected_0_1 = [[0., 0., 0.5],
                      [0., 0., 0.0],
                      [0., 0., 1.0]]
    assert_array_almost_equal(X_trans, X_expected_0_1)
    X_trans_inv = scaler.inverse_transform(X_trans)
    assert_array_almost_equal(X, X_trans_inv)

    X_trans_new = scaler.transform(X_new)
    X_expected_0_1_new = [[+0., 1., 0.500],
                          [-1., 0., 0.083],
                          [+0., 0., 1.333]]
    assert_array_almost_equal(X_trans_new, X_expected_0_1_new, decimal=2)

    # not default params
    scaler = MinMaxScaler(feature_range=(1, 2))
    X_trans = scaler.fit_transform(X)
    X_expected_1_2 = [[1., 1., 1.5],
                      [1., 1., 1.0],
                      [1., 1., 2.0]]
    assert_array_almost_equal(X_trans, X_expected_1_2)


def test_standardscaler_nulltransform():
    rng = np.random.RandomState(42)
    X = rng.randn(4, 5)
    X[:, 0] = 0.0  # first feature is always of zero
    X_csr = sparse.csr_matrix(X)
    null_transform = StandardScaler(with_centering=False,
                                    with_scaling=False, copy=True)
    X_null = null_transform.fit_transform(X_csr)
    assert_array_equal(X_null.data, X_csr.data)
    X_orig = null_transform.inverse_transform(X_null)
    assert_array_equal(X_orig.data, X_csr.data)


def test_robust_scaler_2d_arrays():
    """Test robust scaling of 2d array along first axis"""
    rng = np.random.RandomState(0)
    X = rng.randn(4, 5)
    X[:, 0] = 0.0  # first feature is always of zero

    scaler = RobustScaler()
    X_scaled = scaler.fit(X).transform(X, copy=True)

    assert_array_almost_equal(np.median(X_scaled, axis=0), 5 * [0.0])
    assert_array_almost_equal(X_scaled.std(axis=0)[0], 0)


def test_robust_scaler_iris():
    X = iris.data
    scaler = RobustScaler(interquartile_scale=1.0)
    X_trans = scaler.fit_transform(X)
    assert_array_almost_equal(np.median(X_trans, axis=0), 0)
    X_trans_inv = scaler.inverse_transform(X_trans)
    assert_array_almost_equal(X, X_trans_inv)

    # make sure iqr is 1
    q = mquantiles(X_trans, prob=(0.25, 0.75), axis=0)
    iqr = q[1, :] - q[0, :]
    assert_array_almost_equal(iqr, 1)


def test_robust_scaler_iqr_scale():
    """Does iqr scaling achieve approximately std= 1 on Gaussian data?"""
    rng = np.random.RandomState(42)
    X = rng.randn(10000, 4)  # need lots of samples
    scaler = RobustScaler()
    X_trans = scaler.fit_transform(X)
    assert_array_almost_equal(X_trans.std(axis=0), 1,  decimal=2)


def test_robust_scale_iqr_errors():
    """Check that invalid arguments yield ValueError"""
    rng = np.random.RandomState(42)
    X = rng.randn(4, 5)
    assert_raises(ValueError, RobustScaler(interquartile_scale="foo").fit, X)
    # TODO: for some reason assert_raise doesn't test this correctly
    did_raise = False
    try:
        robust_scale(X, interquartile_scale="foo")
    except ValueError:
        did_raise = True
    assert(did_raise)


def test_robust_scaler_zero_variance_features():
    """Check min max scaler on toy data with zero variance features"""
    X = [[0., 1., +0.5],
         [0., 1., -0.1],
         [0., 1., +1.1]]

    X_new = [[+0., 2., 0.5],
             [-1., 1., 0.0],
             [+0., 1., 1.5]]

    scaler = RobustScaler(interquartile_scale=1.0)
    X_trans = scaler.fit_transform(X)

    # NOTE: what we expect in the third column depends HEAVILY on the method
    # used to calculate quantiles. The values here were calculated
    # to fit the quantiles produces by scipy.stats.mquantiles' default
    # quantile-method. Calculating quantiles with scipy.stats.scoreatquantile
    # would yield very different results!
    X_expected = [[0., 0., +0.0],
                  [0., 0., -0.625],
                  [0., 0., +0.625]]
    assert_array_almost_equal(X_trans, X_expected)
    X_trans_inv = scaler.inverse_transform(X_trans)
    assert_array_almost_equal(X, X_trans_inv)

    X_trans_new = scaler.transform(X_new)
    X_expected_new = [[+0., 1., +0.],
                      [-1., 0., -0.52083],
                      [+0., 0., +1.04166]]
    assert_array_almost_equal(X_trans_new, X_expected_new, decimal=3)


def test_maxabs_scaler_zero_variance_features():
    """Check MaxAbsScaler on toy data with zero variance features"""
    X = [[0., 1., +0.5],
         [0., 1., -0.3],
         [0., 1., +1.5],
         [0., 0., +0.0]]

    X_new = [[+0., 2., 0.5],
             [-1., 1., 0.0],
             [+0., 1., 1.5]]

    # default params
    scaler = MaxAbsScaler()
    X_trans = scaler.fit_transform(X)
    X_expected = [[0., 1., 1.0 / 3.0],
                  [0., 1., -0.2],
                  [0., 1., 1.0],
                  [0., 0., 0.0]]
    assert_array_almost_equal(X_trans, X_expected)
    X_trans_inv = scaler.inverse_transform(X_trans)
    assert_array_almost_equal(X, X_trans_inv)

    X_trans_new = scaler.transform(X_new)
    X_expected_new = [[+0., 2.0, 1.0 / 3.0],
                      [-1., 1.0, 0.0],
                      [+0., 1.0, 1.0]]

    assert_array_almost_equal(X_trans_new, X_expected_new, decimal=2)


def test_maxabs_scaler_large_negative_value():
    """Check MaxAbsScaler on toy data with a large negative value"""
    X = [[0., 1.,   +0.5, -1.0],
         [0., 1.,   -0.3, -0.5],
         [0., 1., -100.0,  0.0],
         [0., 0.,   +0.0, -2.0]]

    scaler = MaxAbsScaler()
    X_trans = scaler.fit_transform(X)
    X_expected = [[0., 1.,  0.005,    -0.5],
                  [0., 1., -0.003,    -0.25],
                  [0., 1., -1.0,       0.0],
                  [0., 0.,  0.0,      -1.0]]
    assert_array_almost_equal(X_trans, X_expected)


def toarray(a):
    if hasattr(a, "toarray"):
        a = a.toarray()
    return a


def test_polynomial_features():
    """Test Polynomial Features"""
    X1 = np.arange(6)[:, np.newaxis]
    P1 = np.hstack([np.ones_like(X1),
                    X1, X1 ** 2, X1 ** 3])
    deg1 = 3

    X2 = np.arange(6).reshape((3, 2))
    x1 = X2[:, :1]
    x2 = X2[:, 1:]
    P2 = np.hstack([x1 ** 0 * x2 ** 0,
                    x1 ** 1 * x2 ** 0,
                    x1 ** 0 * x2 ** 1,
                    x1 ** 2 * x2 ** 0,
                    x1 ** 1 * x2 ** 1,
                    x1 ** 0 * x2 ** 2])
    deg2 = 2

    for (deg, X, P) in [(deg1, X1, P1), (deg2, X2, P2)]:
        P_test = PolynomialFeatures(deg, include_bias=True).fit_transform(X)
        assert_array_almost_equal(P_test, P)

        P_test = PolynomialFeatures(deg, include_bias=False).fit_transform(X)
        assert_array_almost_equal(P_test, P[:, 1:])


def test_normalizer_l1():
    rng = np.random.RandomState(0)
    X_dense = rng.randn(4, 5)
    X_sparse_unpruned = sparse.csr_matrix(X_dense)

    # set the row number 3 to zero
    X_dense[3, :] = 0.0

    # set the row number 3 to zero without pruning (can happen in real life)
    indptr_3 = X_sparse_unpruned.indptr[3]
    indptr_4 = X_sparse_unpruned.indptr[4]
    X_sparse_unpruned.data[indptr_3:indptr_4] = 0.0

    # build the pruned variant using the regular constructor
    X_sparse_pruned = sparse.csr_matrix(X_dense)

    # check inputs that support the no-copy optim
    for X in (X_dense, X_sparse_pruned, X_sparse_unpruned):

        normalizer = Normalizer(norm='l1', copy=True)
        X_norm = normalizer.transform(X)
        assert_true(X_norm is not X)
        X_norm1 = toarray(X_norm)

        normalizer = Normalizer(norm='l1', copy=False)
        X_norm = normalizer.transform(X)
        assert_true(X_norm is X)
        X_norm2 = toarray(X_norm)

        for X_norm in (X_norm1, X_norm2):
            row_sums = np.abs(X_norm).sum(axis=1)
            for i in range(3):
                assert_almost_equal(row_sums[i], 1.0)
            assert_almost_equal(row_sums[3], 0.0)

    # check input for which copy=False won't prevent a copy
    for init in (sparse.coo_matrix, sparse.csc_matrix, sparse.lil_matrix):
        X = init(X_dense)
        X_norm = normalizer = Normalizer(norm='l2', copy=False).transform(X)

        assert_true(X_norm is not X)
        assert_true(isinstance(X_norm, sparse.csr_matrix))

        X_norm = toarray(X_norm)
        for i in range(3):
            assert_almost_equal(row_sums[i], 1.0)
        assert_almost_equal(la.norm(X_norm[3]), 0.0)


def test_normalizer_l2():
    rng = np.random.RandomState(0)
    X_dense = rng.randn(4, 5)
    X_sparse_unpruned = sparse.csr_matrix(X_dense)

    # set the row number 3 to zero
    X_dense[3, :] = 0.0

    # set the row number 3 to zero without pruning (can happen in real life)
    indptr_3 = X_sparse_unpruned.indptr[3]
    indptr_4 = X_sparse_unpruned.indptr[4]
    X_sparse_unpruned.data[indptr_3:indptr_4] = 0.0

    # build the pruned variant using the regular constructor
    X_sparse_pruned = sparse.csr_matrix(X_dense)

    # check inputs that support the no-copy optim
    for X in (X_dense, X_sparse_pruned, X_sparse_unpruned):

        normalizer = Normalizer(norm='l2', copy=True)
        X_norm1 = normalizer.transform(X)
        assert_true(X_norm1 is not X)
        X_norm1 = toarray(X_norm1)

        normalizer = Normalizer(norm='l2', copy=False)
        X_norm2 = normalizer.transform(X)
        assert_true(X_norm2 is X)
        X_norm2 = toarray(X_norm2)

        for X_norm in (X_norm1, X_norm2):
            for i in range(3):
                assert_almost_equal(la.norm(X_norm[i]), 1.0)
            assert_almost_equal(la.norm(X_norm[3]), 0.0)

    # check input for which copy=False won't prevent a copy
    for init in (sparse.coo_matrix, sparse.csc_matrix, sparse.lil_matrix):
        X = init(X_dense)
        X_norm = normalizer = Normalizer(norm='l2', copy=False).transform(X)

        assert_true(X_norm is not X)
        assert_true(isinstance(X_norm, sparse.csr_matrix))

        X_norm = toarray(X_norm)
        for i in range(3):
            assert_almost_equal(la.norm(X_norm[i]), 1.0)
        assert_almost_equal(la.norm(X_norm[3]), 0.0)


def test_normalize_errors():
    """Check that invalid arguments yield ValueError"""
    assert_raises(ValueError, normalize, [[0]], axis=2)
    assert_raises(ValueError, normalize, [[0]], norm='l3')


def test_binarizer():
    X_ = np.array([[1, 0, 5], [2, 3, -1]])

    for init in (np.array, list, sparse.csr_matrix, sparse.csc_matrix):

        X = init(X_.copy())

        binarizer = Binarizer(threshold=2.0, copy=True)
        X_bin = toarray(binarizer.transform(X))
        assert_equal(np.sum(X_bin == 0), 4)
        assert_equal(np.sum(X_bin == 1), 2)
        X_bin = binarizer.transform(X)
        assert_equal(sparse.issparse(X), sparse.issparse(X_bin))

        binarizer = Binarizer(copy=True).fit(X)
        X_bin = toarray(binarizer.transform(X))
        assert_true(X_bin is not X)
        assert_equal(np.sum(X_bin == 0), 2)
        assert_equal(np.sum(X_bin == 1), 4)

        binarizer = Binarizer(copy=True)
        X_bin = binarizer.transform(X)
        assert_true(X_bin is not X)
        X_bin = toarray(X_bin)
        assert_equal(np.sum(X_bin == 0), 2)
        assert_equal(np.sum(X_bin == 1), 4)

        binarizer = Binarizer(copy=False)
        X_bin = binarizer.transform(X)
        if init is not list:
            assert_true(X_bin is X)
        X_bin = toarray(X_bin)
        assert_equal(np.sum(X_bin == 0), 2)
        assert_equal(np.sum(X_bin == 1), 4)

    binarizer = Binarizer(threshold=-0.5, copy=True)
    for init in (np.array, list):
        X = init(X_.copy())

        X_bin = toarray(binarizer.transform(X))
        assert_equal(np.sum(X_bin == 0), 1)
        assert_equal(np.sum(X_bin == 1), 5)
        X_bin = binarizer.transform(X)

    # Cannot use threshold < 0 for sparse
    assert_raises(ValueError, binarizer.transform, sparse.csc_matrix(X))


def test_center_kernel():
    """Test that KernelCenterer is equivalent to StandardScaler
       in feature space"""
    rng = np.random.RandomState(0)
    X_fit = rng.random_sample((5, 4))
    scaler = StandardScaler(with_scaling=False)
    scaler.fit(X_fit)
    X_fit_centered = scaler.transform(X_fit)
    K_fit = np.dot(X_fit, X_fit.T)

    # center fit time matrix
    centerer = KernelCenterer()
    K_fit_centered = np.dot(X_fit_centered, X_fit_centered.T)
    K_fit_centered2 = centerer.fit_transform(K_fit)
    assert_array_almost_equal(K_fit_centered, K_fit_centered2)

    # center predict time matrix
    X_pred = rng.random_sample((2, 4))
    K_pred = np.dot(X_pred, X_fit.T)
    X_pred_centered = scaler.transform(X_pred)
    K_pred_centered = np.dot(X_pred_centered, X_fit_centered.T)
    K_pred_centered2 = centerer.transform(K_pred)
    assert_array_almost_equal(K_pred_centered, K_pred_centered2)


def test_fit_transform():
    rng = np.random.RandomState(0)
    X = rng.random_sample((5, 4))
    for obj in ((StandardScaler(), Normalizer(), Binarizer())):
        X_transformed = obj.fit(X).transform(X)
        X_transformed2 = obj.fit_transform(X)
        assert_array_equal(X_transformed, X_transformed2)


def test_add_dummy_feature():
    X = [[1, 0], [0, 1], [0, 1]]
    X = add_dummy_feature(X)
    assert_array_equal(X, [[1, 1, 0], [1, 0, 1], [1, 0, 1]])


def test_add_dummy_feature_coo():
    X = sparse.coo_matrix([[1, 0], [0, 1], [0, 1]])
    X = add_dummy_feature(X)
    assert_true(sparse.isspmatrix_coo(X), X)
    assert_array_equal(X.toarray(), [[1, 1, 0], [1, 0, 1], [1, 0, 1]])


def test_add_dummy_feature_csc():
    X = sparse.csc_matrix([[1, 0], [0, 1], [0, 1]])
    X = add_dummy_feature(X)
    assert_true(sparse.isspmatrix_csc(X), X)
    assert_array_equal(X.toarray(), [[1, 1, 0], [1, 0, 1], [1, 0, 1]])


def test_add_dummy_feature_csr():
    X = sparse.csr_matrix([[1, 0], [0, 1], [0, 1]])
    X = add_dummy_feature(X)
    assert_true(sparse.isspmatrix_csr(X), X)
    assert_array_equal(X.toarray(), [[1, 1, 0], [1, 0, 1], [1, 0, 1]])


def test_one_hot_encoder_sparse():
    """Test OneHotEncoder's fit and transform."""
    X = [[3, 2, 1], [0, 1, 1]]
    enc = OneHotEncoder()
    # discover max values automatically
    X_trans = enc.fit_transform(X).toarray()
    assert_equal(X_trans.shape, (2, 5))
    assert_array_equal(enc.active_features_,
                       np.where([1, 0, 0, 1, 0, 1, 1, 0, 1])[0])
    assert_array_equal(enc.feature_indices_, [0, 4, 7, 9])

    # check outcome
    assert_array_equal(X_trans,
                       [[0., 1., 0., 1., 1.],
                        [1., 0., 1., 0., 1.]])

    # max value given as 3
    enc = OneHotEncoder(n_values=4)
    X_trans = enc.fit_transform(X)
    assert_equal(X_trans.shape, (2, 4 * 3))
    assert_array_equal(enc.feature_indices_, [0, 4, 8, 12])

    # max value given per feature
    enc = OneHotEncoder(n_values=[3, 2, 2])
    X = [[1, 0, 1], [0, 1, 1]]
    X_trans = enc.fit_transform(X)
    assert_equal(X_trans.shape, (2, 3 + 2 + 2))
    assert_array_equal(enc.n_values_, [3, 2, 2])
    # check that testing with larger feature works:
    X = np.array([[2, 0, 1], [0, 1, 1]])
    enc.transform(X)

    # test that an error is raised when out of bounds:
    X_too_large = [[0, 2, 1], [0, 1, 1]]
    assert_raises(ValueError, enc.transform, X_too_large)
    assert_raises(ValueError, OneHotEncoder(n_values=2).fit_transform, X)

    # test that error is raised when wrong number of features
    assert_raises(ValueError, enc.transform, X[:, :-1])
    # test that error is raised when wrong number of features in fit
    # with prespecified n_values
    assert_raises(ValueError, enc.fit, X[:, :-1])
    # test exception on wrong init param
    assert_raises(TypeError, OneHotEncoder(n_values=np.int).fit, X)

    enc = OneHotEncoder()
    # test negative input to fit
    assert_raises(ValueError, enc.fit, [[0], [-1]])

    # test negative input to transform
    enc.fit([[0], [1]])
    assert_raises(ValueError, enc.transform, [[0], [-1]])


def test_one_hot_encoder_dense():
    """check for sparse=False"""
    X = [[3, 2, 1], [0, 1, 1]]
    enc = OneHotEncoder(sparse=False)
    # discover max values automatically
    X_trans = enc.fit_transform(X)
    assert_equal(X_trans.shape, (2, 5))
    assert_array_equal(enc.active_features_,
                       np.where([1, 0, 0, 1, 0, 1, 1, 0, 1])[0])
    assert_array_equal(enc.feature_indices_, [0, 4, 7, 9])

    # check outcome
    assert_array_equal(X_trans,
                       np.array([[0., 1., 0., 1., 1.],
                                 [1., 0., 1., 0., 1.]]))


def _check_transform_selected(X, X_expected, sel):
    for M in (X, sparse.csr_matrix(X)):
        Xtr = _transform_selected(M, Binarizer().transform, sel)
        assert_array_equal(toarray(Xtr), X_expected)


def test_transform_selected():
    X = [[3, 2, 1], [0, 1, 1]]

    X_expected = [[1, 2, 1], [0, 1, 1]]
    _check_transform_selected(X, X_expected, [0])
    _check_transform_selected(X, X_expected, [True, False, False])

    X_expected = [[1, 1, 1], [0, 1, 1]]
    _check_transform_selected(X, X_expected, [0, 1, 2])
    _check_transform_selected(X, X_expected, [True, True, True])
    _check_transform_selected(X, X_expected, "all")

    _check_transform_selected(X, X, [])
    _check_transform_selected(X, X, [False, False, False])


def _run_one_hot(X, X2, cat):
    enc = OneHotEncoder(categorical_features=cat)
    Xtr = enc.fit_transform(X)
    X2tr = enc.transform(X2)
    return Xtr, X2tr


def _check_one_hot(X, X2, cat, n_features):
    ind = np.where(cat)[0]
    # With mask
    A, B = _run_one_hot(X, X2, cat)
    # With indices
    C, D = _run_one_hot(X, X2, ind)
    # Check shape
    assert_equal(A.shape, (2, n_features))
    assert_equal(B.shape, (1, n_features))
    assert_equal(C.shape, (2, n_features))
    assert_equal(D.shape, (1, n_features))
    # Check that mask and indices give the same results
    assert_array_equal(toarray(A), toarray(C))
    assert_array_equal(toarray(B), toarray(D))


def test_one_hot_encoder_categorical_features():
    X = np.array([[3, 2, 1], [0, 1, 1]])
    X2 = np.array([[1, 1, 1]])

    cat = [True, False, False]
    _check_one_hot(X, X2, cat, 4)

    # Edge case: all non-categorical
    cat = [False, False, False]
    _check_one_hot(X, X2, cat, 3)

    # Edge case: all categorical
    cat = [True, True, True]
    _check_one_hot(X, X2, cat, 5)
