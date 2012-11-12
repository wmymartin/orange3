import unittest
import numpy as np

from Orange import data
from Orange.evaluation.cross import CrossValidation
from Orange.evaluation import scoring
import Orange.classification.naive_bayes as nb
import Orange.classification.linear_regression as lr

class CrossValidationTest(unittest.TestCase):

    def test_KFold_classification(self):
        nrows = 1000
        ncols = 10
        x = np.random.random_integers(1, 3, (nrows, ncols))
        col = np.random.randint(ncols)
        y = x[:nrows,col].reshape(nrows,1)+100
        t = data.Table(x, y)

        cv = CrossValidation(t, nb.BayesLearner())
        z, prob = cv.KFold(3)
        self.assertTrue((z.reshape((-1,1))==y).all())

    def test_KFold_regression(self):
        nrows = 1000
        ncols = 3
        x = np.random.random_integers(-20, 50, (nrows, ncols))
        c = np.random.rand(ncols, 1)*10-3
        e = np.random.rand(nrows, 1)-0.5
        y = np.dot(x,c) + e
        t = data.Table(x, y)

        cv = CrossValidation(t, lr.LinearRegressionLearner())
        z = cv.KFold(3)
        self.assertTrue((abs(z.reshape(-1,1)-y)<2.0).all())

    def test_KFold_probs(self):
        nrows = 19
        ncols = 5
        x = np.random.random_integers(1, 3, (nrows, ncols))
        col = np.random.randint(ncols)
        y = np.random.random_integers(1, 19, (nrows, 1))
        t = data.Table(x, y)

        cv = CrossValidation(t, nb.BayesLearner())
        z, prob = cv.KFold(3)
        self.assertEqual(prob.shape, (nrows, len(t.domain.class_var.values)))

class ScoringTest(unittest.TestCase):

    def testCA(self):
        nrows = 10000
        ncols = 5
        x = np.random.random_integers(1, 3, (nrows, ncols))
        y = np.random.random_integers(1, 2, (nrows, 1))
        t = data.Table(x, y)

        pred = np.random.random_integers(2, 3, nrows)
        self.assertAlmostEqual(scoring.CA(t,pred), 0.25, delta=0.1)

        learn = nb.BayesLearner()
        clf = learn(t)
        pred = clf(x)
        self.assertAlmostEqual(scoring.CA(t,pred), 0.5, delta=0.1)
