import numpy as np
import pymc as mc

from bayesian_models import probabilistic_utils
import beta_binomial_model as rate_model

def rate_key(data_type, region):
    """ Make a human-readable dictionary key"""
    return '%s+%s' % (data_type, region)


def fit(dm, method='map', data_type='prevalence data'):
    """ Generate an estimate of multiregion beta binomial model parameters
    using maximum a posteriori liklihood (MAP) or Markov-chain Monte
    Carlo (MCMC)

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)

    method : string, optional
      the parameter estimation method, either 'map' or 'mcmc'

    data_type : str, optional
      Only data in dm.data with d['data_type'] == data_type will be
      included in each beta-binomial liklihood function

    Example
    -------
    >>> import dismod3
    >>> import dismod3.multiregion_model as model
    >>> dm = dismod3.get_disease_model(847)
    >>> model.fit(dm, method='map')
    >>> model.fit(dm, method='mcmc')
    """
    if not hasattr(dm, 'vars'):
        initialize(dm, data_type)

    if method == 'map':
        if not hasattr(dm, 'map'):
            dm.map = mc.MAP(dm.vars)
        dm.map.fit(method='fmin_powell', iterlim=500, tol=.001, verbose=1)
        for r in dm.data_by_region.keys():
            dm.set_map(rate_key(data_type,r),
                       dm.vars['rate_stochs'][rate_key(data_type,r)].value)
    elif method == 'mcmc':
        if not hasattr(dm, 'mcmc'):
            dm.mcmc = mc.MCMC(dm.vars)
        dm.mcmc.use_step_method(mc.AdaptiveMetropolis, dm.vars['logit_p_stochs'])
        dm.mcmc.sample(iter=4000, burn=1000, thin=3, verbose=1)
        for r in dm.data_by_region.keys():
            rate_model.store_mcmc_fit(dm, mc.vars['rate_stochs'][rate_key(data_type,r)],
                                      rate_key(data_type,r))


def initialize(dm, data_type='prevalence data'):
    """ Initialize the stochastic and deterministic random variables
    for the multiregion beta binomial model of age-specific rate functions

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)

    data_type : str, optional
      Only data in dm.data with d['data_type'] == data_type will be
      included in the beta-binomial liklihood functions
    
    Results
    -------
    * Sets dm's param_age_mesh and estimate_age_mesh, if they are not
      already set.

    * Sets the units of dm

    * Create PyMC variables for the multiregion beta binomial model, and stores
      them in dm.vars
    """
    if dm.get_param_age_mesh() == []:
        dm.set_param_age_mesh([0.0, 10.0, 20.0, 30.0, 40.0,
                               50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
    if dm.get_estimate_age_mesh() == []:
        dm.set_estimate_age_mesh(range(MAX_AGE))

    # sort the data by GBD regions
    dm.data_by_region = {}
    for d in dm.data:
        if d['data_type'] != data_type:
            continue
        r = d['gbd_region']
        dm.data_by_region[r] = dm.data_by_region.get(r, []) + [d]

    # find initial values for the data from each region
    for r, r_data in dm.data_by_region.items():
        # use a random subset of the data if there is a lot of it,
        # to speed things up
        data = [d for d in r_data]
        if len(data) > 25:
            import random
            data = random.sample(data,25)

        dm.set_units(rate_key(data_type, r), '(per person-year)')
        dm.fit_initial_estimate(rate_key(data_type, r), data)

    dm.vars = setup(dm)


def setup(dm, data_type='prevalence data'):
    """ Generate the PyMC variables for a multiregion beta binomial
    model of a rate function that varies by GBD region

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)
      
    data_type : str, optional
      Name stochs according to this string
    
    Results
    -------
    vars : dict of PyMC stochs
      returns a dictionary of all the relevant PyMC objects for the
      beta binomial model.  dm.vars['rate_stochs'] is itself a
      dictionary of stochs, keyed by rate_key(data_type,region).

    Details
    -------
    The beta binomial model models for each regional rate are linked
    together by assuming that they are all realizations of a single
    underlying rate function
    """
    
    rate_stochs = {}
    for r in dm.data_by_region.keys():
        rate_stochs[rate_key(data_type,r)] = \
            rate_model.setup(dm, dm.data_by_region[r], data_type)

    vars = {}
    vars['rate_stochs'] = rate_stochs
    return vars