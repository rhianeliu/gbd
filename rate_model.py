""" Several rate models"""

import pylab as pl
import pymc as mc


def neg_binom_model(name, pi, delta, p, n):
    """ Generate PyMC objects for a negative binomial model

    Parameters
    ----------
    name : str
    pi : pymc.Node, expected values of rates
    delta : pymc.Node, dispersion parameters of rates
    p : array, observed values of rates
    n : array, effective sample sizes of rates

    Results
    -------
    Returns dict of PyMC objects, including 'p_obs' and 'p_pred'
    the observed stochastic likelihood and data predicted stochastic
    """

    @mc.observed(name='p_obs_%s'%name)
    def p_obs(value=p*n, pi=pi, delta=delta, n=n):
        return mc.negative_binomial_like(value, pi*n, delta)

    @mc.deterministic(name='p_pred_%s'%name)
    def p_pred(pi=pi, delta=delta, n=n):
        return mc.rnegative_binomial(pi*n, delta) / pl.array(n, dtype=float)

    return dict(p_obs=p_obs, p_pred=p_pred)


def normal_model(name, pi, sigma, p, s):
    """ Generate PyMC objects for a normal model

    Parameters
    ----------
    name : str
    pi : pymc.Node, expected values of rates
    sigma : pymc.Node, dispersion parameters of rates
    p : array, observed values of rates
    s : array, standard error of rates

    Results
    -------
    Returns dict of PyMC objects, including 'p_obs' and 'p_pred'
    the observed stochastic likelihood and data predicted stochastic
    """

    @mc.observed(name='p_obs_%s'%name)
    def p_obs(value=p, pi=pi, sigma=sigma, s=s):
        return mc.normal_like(p, pi, 1./(sigma**2. + s**2.))

    @mc.deterministic(name='p_pred_%s')
    def p_pred(pi=pi, sigma=sigma, s=s):
        return mc.rnormal(pi, 1./(sigma**2. + s**2.))

    return dict(p_obs=p_obs, p_pred=p_pred)

def log_normal_model(name, pi, sigma, p, s):
    """ Generate PyMC objects for a normal model                                                                                                                                                          

    Parameters
    ----------
    name : str
    pi : pymc.Node, expected values of rates
    sigma : pymc.Node, dispersion parameters of rates
    p : array, observed values of rates
    s : array, standard error sizes of rates

    Results
    -------
    Returns dict of PyMC objects, including 'p_obs' and 'p_pred'
    the observed stochastic likelihood and data predicted stochastic
    """

    @mc.observed(name='p_obs_%s'%name)
    def p_obs(value=p, pi=pi, sigma=sigma, s=s/p):
        return mc.normal_like(pl.log(p), pl.log(pi), 1./(sigma**2. + s**2))

    @mc.deterministic(name='p_pred_%s')
    def p_pred(pi=pi, sigma=sigma, s=s):
        return pl.exp(mc.rnormal(pl.log(pi), 1./(sigma**2. + (s/pi)**2)))

    return dict(p_obs=p_obs, p_pred=p_pred)
