""" Several rate models"""

import pylab as pl
import pymc as mc


def pcgp(name, ages, knots, sigma):
    """ Generate PyMC objects for a piecewise constant Gaussian process (PCGP) model

    Parameters
    ----------
    name : str
    knots : array, locations of the discontinuities in the piecewise constant function
    ages : array, points to interpolate to
    sigma : pymc.Node, smoothness parameter for Matern covariance of GP

    Results
    -------
    Returns dict of PyMC objects, including 'gamma' and 'mu_age'
    the observed stochastic likelihood and data predicted stochastic
    """
    gamma_bar = mc.Normal('gamma_bar_%s'%name, 0., 10.**-2, value=-5.)
    gamma = [mc.Normal('gamma_%s_%d'%(name,k), 0., 10.**-2, value=0) for k in knots]
    gamma[0] = 0.

    import scipy.interpolate
    @mc.deterministic(name='mu_age_%s'%name)
    def mu_age(gamma_bar=gamma_bar, gamma=gamma, knots=knots, ages=ages):
        mu = scipy.interpolate.interp1d(knots, pl.exp(gamma_bar + gamma), 'zero', bounds_error=False, fill_value=0.)
        return mu(ages)

    vars = dict(gamma_bar=gamma_bar, gamma=gamma, mu_age=mu_age, ages=ages, knots=knots)

    if sigma > 0.:
        print 'adding smoothing of', sigma
        @mc.potential(name='smooth_mu_%s'%name)
        def smooth_gamma(gamma=gamma, knots=knots, tau=sigma**-2):
            return mc.normal_like(pl.diff(gamma), 0, tau/pl.diff(knots))
        vars['smooth_gamma'] = smooth_gamma

    return vars
