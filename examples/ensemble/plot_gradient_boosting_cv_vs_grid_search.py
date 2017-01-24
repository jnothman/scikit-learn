"""
===================================================
Gradient Boosting Classifier CV with use_warm_start
===================================================

Gradient boosting is an ensembling technique where several weak learners
(regression trees) are combined to yield a powerful single model, in an
iterative fashion.

:class:`sklearn.model_selection.GridSearch` enables us to
efficiently search for the best number of boosting stages by enabling
``use_warm_start``. This example compares ``GridSearchCV`` performance
for :class:`sklearn.ensemble.GradientBoostingClassifier` with and without
``use_warm_start``.
"""

# Authors: Raghav RV <rvraghav93@gmail.com>
#          Vighnesh Birodkar <vighneshbirodkar@nyu.edu>
#          Joel Nothman <joel.nothman@gmail.com>
# License: BSD 3 clause

import time

import numpy as np
import matplotlib.pyplot as plt

from sklearn.ensemble import GradientBoostingClassifier
from sklearn import datasets
from sklearn.model_selection import GridSearchCV

print(__doc__)

data_list = [datasets.load_iris(return_X_y=True),
             datasets.load_digits(return_X_y=True),
             datasets.make_hastie_10_2()]
names = ['Iris Data', 'Digits Data', 'Hastie Data']

search_n_estimators = range(1, 20)

times = []

for use_warm_start in [False, True]:
    for X, y in data_list:
        gb_gs = GridSearchCV(
            GradientBoostingClassifier(random_state=42),
            param_grid={'n_estimators': search_n_estimators},
            scoring='f1_micro', cv=3, refit=True, verbose=True,
            use_warm_start=use_warm_start).fit(X, y)
        times.append(gb_gs.cv_results_['mean_fit_time'].sum())


plt.figure(figsize=(9, 5))
bar_width = 0.2
n = len(data_list)
index = np.arange(0, n*bar_width, bar_width)*2.5
index = index[0:n]

true_times = times[len(times) // 2:]
false_times = times[:len(times) // 2]


plt.bar(index, true_times, bar_width, label='use_warm_start=True',
        color='green')
plt.bar(index + bar_width, false_times, bar_width,
        label='use_warm_start=False', color='red')

plt.xticks(index + bar_width, names)

plt.legend(loc='best')
plt.grid(True)

plt.xlabel('Datasets')
plt.ylabel('Mean fit time')
plt.show()
