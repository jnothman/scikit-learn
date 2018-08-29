# Authors: Shane Grigsby <refuge@rocktalus.com>
#          Amy X. Zhang <axz@mit.edu>
# License: BSD 3 clause

from __future__ import print_function, division
import numpy as np
import pytest

from sklearn.datasets.samples_generator import make_blobs
from sklearn.cluster.optics_ import OPTICS
from sklearn.cluster.optics_ import _TreeNode, _cluster_tree
from sklearn.cluster.optics_ import _find_local_maxima
from sklearn.metrics.cluster import contingency_matrix
from sklearn.cluster.dbscan_ import DBSCAN
from sklearn.utils.testing import assert_equal, assert_warns
from sklearn.utils.testing import assert_array_almost_equal
from sklearn.utils.testing import assert_array_equal
from sklearn.utils.testing import assert_raise_message

from sklearn.cluster.tests.common import generate_clustered_data


rng = np.random.RandomState(0)
n_points_per_cluster = 250
C1 = [-5, -2] + .8 * rng.randn(n_points_per_cluster, 2)
C2 = [4, -1] + .1 * rng.randn(n_points_per_cluster, 2)
C3 = [1, -2] + .2 * rng.randn(n_points_per_cluster, 2)
C4 = [-2, 3] + .3 * rng.randn(n_points_per_cluster, 2)
C5 = [3, -2] + 1.6 * rng.randn(n_points_per_cluster, 2)
C6 = [5, 6] + 2 * rng.randn(n_points_per_cluster, 2)
X = np.vstack((C1, C2, C3, C4, C5, C6))


def test_correct_number_of_clusters():
    # in 'auto' mode

    n_clusters = 3
    X = generate_clustered_data(n_clusters=n_clusters)
    # Parameters chosen specifically for this task.
    # Compute OPTICS
    clust = OPTICS(max_bound=5.0 * 6.0, min_samples=4, metric='euclidean')
    clust.fit(X)
    # number of clusters, ignoring noise if present
    n_clusters_1 = len(set(clust.labels_)) - int(-1 in clust.labels_)
    assert_equal(n_clusters_1, n_clusters)


def test_minimum_number_of_sample_check():
    # test that we check a minimum number of samples
    msg = ("Number of training samples (n_samples=1) must be greater than "
           "min_samples (min_samples=10) used for clustering.")

    # Compute OPTICS
    X = [[1, 1]]
    clust = OPTICS(max_bound=5.0 * 0.3, min_samples=10)

    # Run the fit
    assert_raise_message(ValueError, msg, clust.fit, X)


def test_empty_extract():
    # Test extract where fit() has not yet been run.
    msg = ("This OPTICS instance is not fitted yet. Call 'fit' with "
           "appropriate arguments before using this method.")
    clust = OPTICS(max_bound=5.0 * 0.3, min_samples=10)
    assert_raise_message(ValueError, msg, clust.extract_dbscan, 0.01)


def test_bad_extract():
    # Test an extraction of eps too close to original eps
    msg = "Specify an epsilon smaller than 0.015. Got 0.3."
    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    # Compute OPTICS
    clust = OPTICS(max_bound=5.0 * 0.003, min_samples=10)
    clust2 = clust.fit(X)
    assert_raise_message(ValueError, msg, clust2.extract_dbscan, 0.3)


def test_close_extract():
    # Test extract where extraction eps is close to scaled epsPrime

    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    # Compute OPTICS
    clust = OPTICS(max_bound=1.0, min_samples=10)
    clust3 = clust.fit(X)
    # check warning when centers are passed
    assert_warns(RuntimeWarning, clust3.extract_dbscan, .3)
    # Cluster ordering starts at 0; max cluster label = 2 is 3 clusters
    assert_equal(max(clust3.extract_dbscan(.3)[1]), 2)


@pytest.mark.parametrize('eps', [0.1, .3, .5])
@pytest.mark.parametrize('min_samples', [3, 10, 20])
def test_dbscan_optics_parity(eps, min_samples):
    # Test that OPTICS clustering labels are <= 5% difference of DBSCAN

    centers = [[1, 1], [-1, -1], [1, -1]]
    X, labels_true = make_blobs(n_samples=750, centers=centers,
                                cluster_std=0.4, random_state=0)

    # calculate optics with dbscan extract at 0.3 epsilon
    op = OPTICS(min_samples=min_samples).fit(X)
    core_optics, labels_optics = op.extract_dbscan(eps)

    # calculate dbscan labels
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(X)

    contingency = contingency_matrix(db.labels_, labels_optics)
    agree = min(np.sum(np.max(contingency, axis=0)),
                np.sum(np.max(contingency, axis=1)))
    disagree = X.shape[0] - agree

    # verify core_labels match
    assert_array_equal(core_optics, db.core_sample_indices_)

    non_core_count = len(labels_optics) - len(core_optics)
    percent_mismatch = np.round((disagree - 1) / non_core_count, 2)

    # verify label mismatch is <= 5% labels
    assert percent_mismatch <= 0.05


def test_auto_extract_hier():
    # Tests auto extraction gets correct # of clusters with varying density
    clust = OPTICS(min_samples=9).fit(X)
    assert_equal(len(set(clust.labels_)), 6)


# try arbitrary minimum sizes
@pytest.mark.parametrize('min_cluster_size', range(2, X.shape[0] // 10, 23))
def test_min_cluster_size(min_cluster_size):
    redX = X[::10]  # reduce for speed
    clust = OPTICS(min_samples=9, min_cluster_size=min_cluster_size).fit(redX)
    cluster_sizes = np.bincount(clust.labels_[clust.labels_ != -1])
    if cluster_sizes.size:
        assert min(cluster_sizes) >= min_cluster_size
    # check behaviour is the same when min_cluster_size is a fraction
    clust_frac = OPTICS(min_samples=9,
                        min_cluster_size=min_cluster_size / redX.shape[0])
    clust_frac.fit(redX)
    assert_array_equal(clust.labels_, clust_frac.labels_)


@pytest.mark.parametrize("reach, n_child, members", [
    (np.array([np.inf, 0.9, 0.9, 1.0, 0.89, 0.88, 10, .9, .9, .9, 10, 0.9,
               0.9, 0.89, 0.88, 10, .9, .9, .9, .9]), 2, np.r_[0:6]),
    (np.array([np.inf, 0.9, 0.9, 0.9, 0.89, 0.88, 10, .9, .9, .9, 10, 0.9,
               0.9, 0.89, 0.88, 100, .9, .9, .9, .9]), 1, np.r_[0:15])])
def test_cluster_sigmin_pruning(reach, n_child, members):
    # Tests pruning left and right, insignificant splitpoints, empty nodelists
    # Parameters chosen specifically for this task

    # Case 1: Three pseudo clusters, 2 of which are too small
    # Case 2: Two pseudo clusters, 1 of which are too small
    # Normalize
    reach = reach / np.max(reach[1:])

    ordering = np.r_[0:20]
    cluster_boundaries = _find_local_maxima(reach, 5)
    root = _TreeNode(ordering, 0, 20, None)

    # Build cluster tree inplace on root node
    _cluster_tree(root, None, cluster_boundaries, reach, ordering,
                  5, .75, .7, .4, .3)
    assert_equal(root.split_point, cluster_boundaries[0])
    assert_equal(n_child, len(root.children))
    assert_array_equal(members, root.children[0].points)


def test_reach_dists():
    # Tests against known extraction array

    clust = OPTICS(min_samples=10, metric='minkowski').fit(X)

    # Expected values, matches 'RD' results from:
    # http://chemometria.us.edu.pl/download/optics.py

    v = [np.inf, 0.606005, 0.472013, 0.162951, 0.161000, 0.385547, 0.179715,
         0.213507, 0.348468, 0.308146, 0.560519, 0.266072, 0.764384, 0.253164,
         0.435716, 0.153696, 0.363924, 0.194267, 0.392313, 0.230589, 0.260023,
         0.535348, 0.168173, 0.296736, 0.310583, 0.277204, 0.250654, 0.153696,
         0.215533, 0.175710, 0.168173, 0.283134, 0.256372, 0.313931, 0.234164,
         0.179715, 0.352957, 0.277052, 0.180986, 0.203819, 0.296022, 0.356691,
         0.515438, 0.219208, 0.265821, 0.346630, 0.275305, 0.229332, 0.433715,
         0.153696, 0.584960, 0.265821, 0.471049, 0.259154, 0.461707, 0.400021,
         0.422748, 0.300699, 0.162951, 0.290504, 0.315199, 0.327130, 0.168864,
         0.462826, 0.188862, 0.259784, 0.216788, 0.259784, 0.195673, 0.315199,
         0.313931, 0.189128, 0.461707, 0.265821, 0.233594, 0.433715, 0.222260,
         0.251734, 0.352957, 0.218134, 0.453792, 0.179715, 0.296736, 0.260023,
         0.311162, 0.214549, 0.266072, 0.318744, 0.180986, 0.194267, 0.262882,
         0.420186, 0.352957, 0.288388, 0.360962, 0.328054, 0.293849, 0.198271,
         0.248772, 0.461707, 0.216788, 0.396450, 0.352957, 0.289448, 0.241311,
         0.213742, 0.220516, 0.218134, 0.153696, 0.516090, 0.218134, 0.221507,
         0.328647, 0.255933, 0.195766, 0.233594, 0.205270, 0.296736, 0.726008,
         0.251991, 0.168173, 0.214027, 0.262882, 0.342089, 0.260023, 0.266072,
         0.253164, 0.230345, 0.262882, 0.296022, 0.227047, 0.205974, 0.328647,
         0.184315, 0.196304, 0.831185, 0.514116, 0.168173, 0.189784, 0.664306,
         0.327130, 0.379139, 0.208932, 0.266140, 0.362751, 0.168173, 0.764384,
         0.327130, 0.187107, 0.194267, 0.414196, 0.251734, 0.220516, 0.363924,
         0.166886, 0.327130, 0.233594, 0.203819, 0.230589, 0.203819, 0.222972,
         0.311526, 0.218134, 0.422748, 0.314870, 0.315199, 0.315199, 0.594179,
         0.328647, 0.415638, 0.244046, 0.250654, 0.214027, 0.203819, 0.213507,
         0.260023, 0.311442, 0.168173, 0.389432, 0.229343, 0.162951, 0.311162,
         0.153696, 0.214027, 0.250654, 0.315199, 0.172484, 0.153696, 0.352957,
         0.314870, 0.328647, 0.546505, 0.378118, 0.260023, 0.387830, 0.199714,
         0.262882, 0.250654, 0.345254, 0.396450, 0.250654, 0.179715, 0.328647,
         0.179715, 0.263104, 0.265821, 0.231714, 0.514116, 0.213507, 0.474255,
         0.212568, 0.376760, 0.196304, 0.844945, 0.194267, 0.264914, 0.210320,
         0.316374, 0.184315, 0.179715, 0.250654, 0.153696, 0.162951, 0.315199,
         0.179965, 0.297876, 0.213507, 0.475420, 0.439372, 0.241311, 0.260927,
         0.194267, 0.422748, 0.222260, 0.411940, 0.414733, 0.260923, 0.396450,
         0.380672, 0.333277, 0.290504, 0.196014, 0.844945, 0.506989, 0.153696,
         0.218134, 0.392313, 0.698970, 0.168173, 0.227047, 0.028856, 0.033243,
         0.028506, 0.057003, 0.038335, 0.051183, 0.063923, 0.022363, 0.030677,
         0.036155, 0.017748, 0.062887, 0.036041, 0.051183, 0.078198, 0.068936,
         0.032418, 0.040634, 0.022188, 0.022112, 0.036858, 0.040199, 0.025549,
         0.083975, 0.032209, 0.025525, 0.032952, 0.034727, 0.068887, 0.040634,
         0.048985, 0.047450, 0.022422, 0.023767, 0.028092, 0.047450, 0.029202,
         0.026105, 0.030542, 0.032250, 0.062887, 0.038335, 0.026753, 0.028092,
         0.099391, 0.021430, 0.020496, 0.021430, 0.025043, 0.023868, 0.050069,
         0.023868, 0.044140, 0.038032, 0.022112, 0.044140, 0.031528, 0.028092,
         0.020065, 0.055926, 0.031508, 0.025549, 0.028062, 0.036155, 0.023694,
         0.029423, 0.026105, 0.028497, 0.023868, 0.044808, 0.035783, 0.033090,
         0.038779, 0.032146, 0.038421, 0.057328, 0.020065, 0.020065, 0.028858,
         0.021337, 0.041226, 0.022507, 0.028506, 0.030257, 0.057912, 0.050876,
         0.120109, 0.020065, 0.034727, 0.038596, 0.037008, 0.031609, 0.095640,
         0.083728, 0.064906, 0.030677, 0.057003, 0.037008, 0.018705, 0.030677,
         0.044140, 0.034727, 0.045226, 0.032146, 0.032418, 0.029332, 0.030104,
         0.033243, 0.030104, 0.032209, 0.026405, 0.024092, 0.048441, 0.036379,
         0.030745, 0.023454, 0.018705, 0.124248, 0.041114, 0.020700, 0.042633,
         0.042455, 0.028497, 0.029202, 0.057859, 0.053157, 0.036155, 0.029534,
         0.032209, 0.038032, 0.024617, 0.023071, 0.033090, 0.023694, 0.047277,
         0.024617, 0.023868, 0.043916, 0.025549, 0.046198, 0.041086, 0.042003,
         0.022507, 0.021430, 0.038779, 0.025043, 0.036379, 0.036326, 0.029421,
         0.023454, 0.058683, 0.025549, 0.039904, 0.022507, 0.046198, 0.029332,
         0.032209, 0.036155, 0.038421, 0.025043, 0.023694, 0.030104, 0.022363,
         0.048544, 0.035180, 0.030677, 0.022112, 0.030677, 0.036678, 0.022507,
         0.024092, 0.064231, 0.022507, 0.032209, 0.025043, 0.221152, 0.029840,
         0.038779, 0.040634, 0.024617, 0.032418, 0.025525, 0.033298, 0.028092,
         0.045754, 0.032209, 0.017748, 0.033090, 0.017748, 0.048931, 0.038689,
         0.022112, 0.027129, 0.032952, 0.036858, 0.027704, 0.032146, 0.052191,
         0.042633, 0.071638, 0.044140, 0.022507, 0.046647, 0.028270, 0.050525,
         0.036772, 0.058995, 0.038335, 0.025185, 0.022507, 0.040293, 0.032418,
         0.064308, 0.026023, 0.036155, 0.032418, 0.038032, 0.018705, 0.040293,
         0.030104, 0.030845, 0.064906, 0.025525, 0.036155, 0.022507, 0.022363,
         0.032418, 0.021430, 0.032209, 0.102770, 0.036960, 0.031062, 0.025043,
         0.036155, 0.031609, 0.036379, 0.030845, 0.048985, 0.021848, 0.025549,
         0.022507, 0.035783, 0.023698, 0.034422, 0.032418, 0.022507, 0.023868,
         0.020065, 0.023694, 0.040634, 0.055633, 0.054549, 0.044662, 0.087660,
         0.048066, 0.143571, 0.068669, 0.065049, 0.076927, 0.044359, 0.041577,
         0.052364, 0.100317, 0.062146, 0.067578, 0.054549, 0.047239, 0.062809,
         0.033917, 0.087660, 0.077113, 0.055633, 0.061854, 0.059756, 0.059537,
         0.052364, 0.060347, 0.170251, 0.108492, 0.046370, 0.070684, 0.049589,
         0.044662, 0.049013, 0.043303, 0.069573, 0.075044, 0.054354, 0.065072,
         0.073135, 0.046126, 0.055569, 0.047239, 0.062146, 0.056093, 0.059986,
         0.096182, 0.100317, 0.051649, 0.054354, 0.077420, 0.100317, 0.046370,
         0.043303, 0.045845, 0.061422, 0.091580, 0.206234, 0.051405, 0.071684,
         0.061574, 0.063666, 0.052692, 0.051649, 0.100124, 0.077909, 0.033917,
         0.058680, 0.044359, 0.065498, 0.080214, 0.123231, 0.052957, 0.056582,
         0.061540, 0.076794, 0.043303, 0.054884, 0.044359, 0.145249, 0.081741,
         0.041577, 0.056093, 0.076799, 0.044359, 0.068483, 0.051649, 0.092275,
         0.044359, 0.108492, 0.092275, 0.046126, 0.106422, 0.054354, 0.052957,
         0.073329, 0.046126, 0.086402, 0.048194, 0.128569, 0.104042, 0.061854,
         0.069573, 0.070035, 0.050346, 0.043303, 0.053576, 0.054549, 0.033917,
         0.063666, 0.058680, 0.099130, 0.080198, 0.050118, 0.054549, 0.041577,
         0.143571, 0.095965, 0.047643, 0.052364, 0.105168, 0.048685, 0.043303,
         0.052814, 0.076927, 0.054549, 0.041577, 0.066657, 0.189930, 0.046370,
         0.075044, 0.121331, 0.043303, 0.223897, 0.198621, 0.150328, 0.100317,
         0.053576, 0.070708, 0.100898, 0.047239, 0.043613, 0.065049, 0.049146,
         0.068669, 0.055569, 0.062124, 0.096408, 0.044662, 0.087660, 0.083012,
         0.050118, 0.069573, 0.046126, 0.049146, 0.049146, 0.050808, 0.080198,
         0.059986, 0.071974, 0.047239, 0.050808, 0.059986, 0.065850, 0.044863,
         0.052814, 0.044359, 0.052364, 0.108492, 0.143571, 0.050926, 0.049146,
         0.049146, 0.055569, 0.033917, 0.527659, 0.143547, 0.077113, 0.046126,
         0.106422, 0.068669, 0.108492, 0.063666, 0.054549, 0.054884, 0.056907,
         0.068669, 0.080198, 0.120887, 0.054549, 0.052692, 0.085801, 0.054884,
         0.050808, 0.094595, 0.059545, 0.054354, 0.062124, 0.087660, 0.052814,
         0.086715, 0.146253, 0.046370, 0.041577, 0.116083, 0.076927, 0.047239,
         0.084375, 0.134652, 0.217969, 0.063559, 0.061540, 0.044662, 0.054354,
         0.063666, 0.145466, 0.101700, 0.090491, 0.078536, 0.054884, 0.062124,
         0.041577, 0.043303, 0.194473, 0.079780, 0.059704, 0.054780, 0.048194,
         0.062146, 0.069573, 0.086898, 0.046675, 0.056258, 0.074141, 0.048066,
         0.052957, 0.057982, 0.058966, 0.061048, 0.050885, 0.049146, 0.080993,
         0.056093, 0.061854, 0.124025, 0.062146, 0.060906, 0.150328, 0.058680,
         0.077420, 0.051800, 0.102359, 0.113301, 0.073096, 0.116715, 0.131476,
         0.140601, 0.097667, 0.051800, 0.051800, 0.127964, 0.108870, 0.111926,
         0.093532, 0.102390, 0.144266, 0.098271, 0.102541, 0.136497, 0.127964,
         0.085569, 0.157863, 0.096739, 0.054008, 0.106219, 0.076838, 0.099076,
         0.093532, 0.059861, 0.079975, 0.116715, 0.133625, 0.053641, 0.066110,
         0.122302, 0.081313, 0.140601, 0.259889, 0.094437, 0.098271, 0.105776,
         0.225742, 0.100097, 0.147592, 0.099076, 0.093128, 0.093532, 0.134946,
         0.133625, 0.120869, 0.065932, 0.103395, 0.125172, 0.147842, 0.105278,
         0.173584, 0.168241, 0.111524, 0.093532, 0.099076, 0.100426, 0.137132,
         0.065356, 0.091108, 0.141202, 0.054008, 0.075298, 0.073717, 0.122817,
         0.105278, 0.094437, 0.067080, 0.108530, 0.115467, 0.093532, 0.085569,
         0.145180, 0.100426, 0.116715, 0.151726, 0.073096, 0.193781, 0.090614,
         0.081162, 0.051800, 0.133625, 0.136497, 0.100670, 0.081313, 0.506893,
         0.084567, 0.108530, 0.087353, 0.063184, 0.123639, 0.168333, 0.314422,
         0.091108, 0.079975, 0.091108, 0.136497, 0.122302, 0.167297, 0.067080,
         0.144266, 0.065932, 0.087667, 0.100426, 0.099460, 0.091108, 0.100637,
         0.116715, 0.079975, 0.077977, 0.090340, 0.136723, 1.943026, 0.108870,
         0.090340, 0.065932, 0.102245, 0.157863, 0.157863, 0.215574, 0.156830,
         0.093532, 0.122302, 0.097667, 0.063000, 0.116715, 0.076838, 0.148372,
         0.093532, 0.099076, 0.141202, 0.096505, 0.096739, 0.091108, 0.099076,
         0.079975, 0.108870, 0.102390, 0.079975, 0.244121, 0.167071, 0.096739,
         0.102390, 0.103395, 0.073096, 0.094887, 0.065932, 0.190667, 0.099460,
         0.102390, 0.096739, 0.102390, 0.116715, 0.100637, 0.256554, 0.103395,
         0.081313, 0.068962, 0.109645, 0.059364, 0.147842, 0.099460, 0.079262,
         0.099460, 0.065932, 0.123687, 0.090614, 0.131352, 0.098271, 0.102541,
         0.098983, 0.057224, 0.074797, 0.057224, 0.250559, 0.079975, 0.103395,
         0.100426, 0.065932, 0.120661, 0.079262, 0.065932, 0.118665, 0.081162,
         0.066283, 0.099076, 0.102359, 0.108530, 0.079975, 0.168333, 0.096739,
         0.168333, 0.097008, 0.055288, 0.172411, 0.092801, 0.051800, 0.102541,
         0.084567, 0.054008, 0.090991, 0.172411, 0.057224, 0.148396, 0.200965,
         0.076838, 0.157863, 0.053535, 0.121919, 0.126609, 0.123890, 0.118081,
         0.097008, 0.125311, 0.099460, 0.122302, 0.134946, 0.080975, 0.084567,
         0.110093, 0.102245, 0.103395, 0.171601, 0.094887, 0.126240, 0.137742,
         0.099954, 0.108530, 0.157863, 0.096739, 0.051800, 0.127964, 0.066110,
         0.061021, 0.105147, 0.100426, 0.079975, 0.088187, 0.116421, 0.076838,
         0.098271, 0.116715, 0.137656, 0.075298, 0.148396, 0.112166, 1.083905,
         0.326598, 0.428987, 0.395963, 0.224541, 0.326598, 0.030677, 0.410454,
         0.122771, 1.140305, 0.641074, 0.432159, 0.429335, 0.422908, 0.461926,
         0.293083, 0.477078, 0.714856, 0.515861, 0.405418, 0.054354, 0.341177,
         0.410008, 0.514245, 0.641074, 0.816459, 0.455115, 0.400707, 0.382240,
         0.431832, 1.618970, 0.683953, 0.182992, 0.763699, 0.515861, 0.717145,
         0.409629, 0.074134, 0.398273, 0.864974, 0.400707, 0.591403, 0.435354,
         0.514245, 1.337152, 0.841077, 0.410008, 0.683953, 0.338649, 0.557595,
         0.442092, 0.326598, 0.984189, 0.429608, 0.395963, 1.152055, 0.587222,
         1.748492, 0.477078, 0.395459, 0.717145, 0.575811, 0.210115, 0.487785,
         0.431832, 0.383852, 0.806708, 0.428987, 0.278405, 0.395963, 0.395459,
         0.383852, 1.083905, 0.428510, 0.326598, 0.108492, 0.541644, 0.612110,
         0.382240, 0.833511, 0.382240, 0.456628, 0.326598, 0.458880, 0.398273,
         0.957748, 0.326598, 0.295049, 0.629646, 0.429765, 0.439942, 0.633617,
         0.566297, 0.429335, 0.086507, 0.477078, 0.526753, 0.375240, 0.584436,
         0.355776, 0.395963, 0.644924, 0.129793, 0.484880, 0.470001, 0.572306,
         0.383852, 1.110081, 0.841077, 0.395963, 0.683953, 0.428745, 0.387752,
         0.545299, 0.686537, 0.635219, 0.840499, 0.527659, 0.400707, 0.480982,
         0.541644, 0.714856, 0.942673, 0.398273, 0.428987, 0.356781, 0.428510,
         1.140961, 0.395963, 0.356781, 0.410454, 0.541644, 0.641074, 0.484778,
         0.410008, 0.433108, 0.278405, 0.278405, 0.503141, 0.428745, 0.125103,
         0.633617, 0.410454, 0.124025, 0.461926, 0.398273, 0.410008, 1.181303,
         0.635219, 0.593537, 0.395963, 0.717145, 0.409629, 0.492595, 0.806708,
         0.503820, 0.423834, 0.557595, 0.429335, 0.470749, 0.461926, 1.890036,
         0.236343, 0.806708, 0.123561, 0.433744, 0.427348, 0.427348, 0.962234,
         0.395963, 0.409629, 0.527659, 0.425727, 0.602549, 0.901331, 0.326598,
         0.635949, 0.541644, 0.375240, 0.598969, 1.140961, 0.391998, 0.719443,
         0.410008, 0.515861, 0.714856, 0.842273, 0.410454, 0.389377, 0.431078,
         0.515861, 0.515861, 0.429335, 0.332495, 0.398273, 0.428987, 0.635219,
         0.387752, 0.384289, 0.383852, 0.430504, 0.428510, 0.431832, 0.375240,
         0.278405, 0.374102, 0.428745, 0.692878, 1.152055, 0.503820, 0.428745,
         0.352868, 0.429335, 0.375240, 0.400707, 0.427348, 0.256183, 0.962234,
         0.505376, 0.058995, 0.410454, 0.172880, 0.395963, 0.470749, 0.356781,
         1.332700, 0.683953, 0.395963, 0.806708, 0.400707, 0.330982, 0.427731,
         0.934845, 0.375240, 0.191534, 0.047239, 1.083905, 0.348794, 0.409708,
         0.503820, 0.557595, 0.429335, 0.498780, 0.293083, 0.363069, 0.442092,
         1.152055, 0.375240, 0.335677, 0.452443, 0.655156, 0.929928, 0.614869,
         1.411031, 1.101132, 0.469030, 0.404976, 0.538209, 0.655828, 0.674748,
         0.365182, 0.641612, 0.555434, 0.521651, 0.386679, 0.386679, 0.980304,
         0.659111, 0.651366, 0.538209, 0.521651, 0.884780, 1.287829, 0.558322,
         0.446161, 0.817970, 0.568499, 0.533507, 0.639746, 0.484404, 0.591751,
         0.913016, 0.446161, 0.533907, 0.606885, 0.672320, 1.150642, 0.655828,
         0.365182, 0.665088, 1.094242, 0.629401, 0.540676, 0.733026, 1.248265,
         1.273499, 0.867854, 0.538656, 0.386679, 0.922273, 0.515686, 1.321022,
         0.624444, 0.655828, 0.922273, 0.386679, 0.762191, 0.779432, 0.601851,
         0.655156, 0.926213, 0.762191, 0.641612, 0.558322, 1.025370, 0.641067,
         0.651366, 0.633434, 0.459580, 0.859221, 0.552291, 0.591751, 0.819965,
         0.669977, 1.185083, 0.499338, 0.533907, 0.752871, 0.571388, 0.539772,
         0.449182, 1.025370, 0.365182, 1.321022, 0.926213, 0.886360, 0.562272,
         0.669977, 0.796046, 0.557598, 0.596776, 0.672336, 0.659111, 0.453719,
         0.477716, 0.477716, 1.592069, 0.591751, 0.539772, 0.641612, 0.946254,
         0.744165, 0.386679, 0.593825, 0.539772, 0.449182, 0.604273, 0.794951,
         0.752871, 0.539772, 0.648732, 0.469030, 0.665088, 1.332700, 1.341388,
         0.533507, 0.544212, 1.025992, 0.645967, 0.612945, 0.868492, 0.648732,
         0.752300, 0.624444, 1.219748, 0.446161, 0.520818, 0.469044, 0.669977,
         0.926213, 0.638752, 0.762191, 0.922273, 0.794951, 0.606885, 0.669977,
         0.550113, 0.641067, 0.733026, 0.604273, 0.648732, 0.533507, 0.746506,
         0.733026, 0.980683, 0.538209, 0.669977, 0.469030, 0.648732, 0.609190,
         1.219748, 0.373113, 0.539772, 1.744047, 1.004716, 0.926213, 0.562272,
         0.752871, 0.538656, 0.449182, 0.365182, 0.469030, 0.446161, 0.484404,
         0.768592, 0.648732, 0.655156, 0.521651, 0.779432, 0.446161, 0.596776,
         0.538209, 0.726740, 0.539772, 0.469030, 0.521651, 0.561950, 0.601851,
         0.533907, 0.922273, 1.248265, 0.476800, 0.737990, 0.817970, 0.792127,
         0.533907, 0.486038, 0.624444, 0.798241, 0.476800, 1.059373, 0.645967,
         0.619940, 0.528726, 0.669977, 0.865406, 0.980683, 0.980683, 0.834671,
         1.001353, 0.752871, 0.449182, 1.096520, 0.449182, 0.593825, 0.636558,
         0.762191, 0.638591, 0.538209, 0.865406, 0.779432, 0.469044, 0.645967,
         0.557598, 0.499338, 0.484404, 0.515686, 0.794951, 0.619456, 0.733026,
         0.821769, 0.752300, 0.643302, 0.636558, 0.655156, 0.655156, 0.484404,
         0.648732, 0.726023, 0.365182, 0.606885, 0.499338, 0.520818, 0.612945,
         0.446161, 0.557598, 0.469044, 1.134650, 0.629401, 0.538656, 0.561950,
         1.364861, 0.459580, 1.025370, 0.980304, 0.607592, 0.533907, 1.134650,
         0.446161, 0.629962]

    assert_array_almost_equal(clust.reachability_, np.array(v))
