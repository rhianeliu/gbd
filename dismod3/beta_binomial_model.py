import numpy as np
import pymc as mc
import random

from dismod3.utils import trim, interpolate, rate_for_range, indices_for_range, generate_prior_potentials
from dismod3.settings import NEARLY_ZERO, MISSING

def fit(dm, method='map', param_type='prevalence', units='(per 1.0)'):
    """ Generate an estimate of the beta binomial model parameters
    using maximum a posteriori liklihood (MAP) or Markov-chain Monte
    Carlo (MCMC).

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      The object containing all the data, priors, and additional
      information (like input and output age-mesh).

    method : string, optional
      The parameter estimation method, either 'map' or 'mcmc'.

    param_type : str, optional
      Only data in dm.data with clean(d['data_type']).find(param_type) != -1
      will be included in the beta-binomial liklihood function.

    units : str, optional
      The units of this parameter, for pretty plotting, etc.

    Example
    -------
    >>> import dismod3
    >>> import dismod3.beta_binomial_model as model
    >>> dm = dismod3.get_disease_model(1)
    >>> model.fit(dm, method='map', param_type='case-fatality', units='(per person-year)')
    >>> model.fit(dm, method='mcmc', param_type='case-fatality', units='(per person-year)')
    """

    # setup model variables, if they do not already exist
    if not hasattr(dm, 'vars'):
        data =  [d for d in dm.data if clean(d['data_type']).find(param_type) != -1]
        # use a random subset of the data if there is a lot of it,
        # to speed things up
        if len(data) > 25:
            dm.fit_initial_estimate(param_type, random.sample(data,25))
        else:
            dm.fit_initial_estimate(param_type, data)

        dm.set_units(param_type, units)

        dm.vars = setup(dm, param_type, data)

    # fit the model, with the selected method
    if method == 'map':
        if not hasattr(dm, 'map'):
            dm.map = mc.MAP(dm.vars)
        dm.map.fit(method='fmin_powell', iterlim=500, tol=.001, verbose=1)
        dm.set_map(param_type, dm.vars['rate_stoch'].value)
    elif method == 'mcmc':
        if not hasattr(dm, 'mcmc'):
            dm.mcmc = mc.MCMC(dm.vars)
        if len(dm.vars['logit_p_stochs']) > 0:
            dm.mcmc.use_step_method(mc.AdaptiveMetropolis, dm.vars['logit_p_stochs'])
        dm.mcmc.sample(iter=40000, burn=10000, thin=30, verbose=1)
        store_mcmc_fit(dm, param_type, dm.vars['rate_stoch'])


def store_mcmc_fit(dm, key, rate_stoch):
    """ Store the parameter estimates generated by an MCMC fit of the
    beta-binomial model in the disease_model object, keyed by key
    
    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)

    key : str

    rate_stoch : PyMC stochastic or deterministic variable

    Results
    -------
    Save a sketch of the distribution of rate_stoch keyed by key.

    Notes
    -----
    This method will be used by other models that have beta binomial
    parts as building blocks, so don't simplify the parameters, at
    least not without thinking about where else the function might
    need to be used
    """
    rate = rate_stoch.trace()
    trace_len = len(rate)
    age_len = len(dm.get_estimate_age_mesh())
    
    sr = []
    # TODO: use rate_stoch.stats() to get these statistics, instead of roll-me-own
    for ii in xrange(age_len):
        sr.append(sorted(rate[:,ii]))
    dm.set_mcmc('lower_ui', key, [sr[ii][int(.025*trace_len)] for ii in xrange(age_len)])
    dm.set_mcmc('median', key, [sr[ii][int(.5*trace_len)] for ii in xrange(age_len)])
    dm.set_mcmc('upper_ui', key, [sr[ii][int(.975*trace_len)] for ii in xrange(age_len)])
    dm.set_mcmc('mean', key, np.mean(rate, 0))

    if dm.vars[key].has_key('conf'):
        dm.set_mcmc('confidence', key, dm.vars[key]['conf'].stats()['quantiles'].values())
    elif dm.vars[key].has_key('logit_sys_err'):
        dm.set_mcmc('confidence', key, dm.vars[key]['logit_sys_err'].stats()['quantiles'].values())

def setup(dm, key, data_list, rate_stoch=None):
    """ Generate the PyMC variables for a beta binomial model of
    a single rate function

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)
      
    key : str
      the name of the key for everything about this model (priors,
      initial values, estimations)

    data_list : list of data dicts
      the observed data to use in the beta-binomial liklihood function

    rate_stoch : pymc.Stochastic, optional
      a PyMC stochastic (or deterministic) object, with
      len(rate_stoch.value) == len(dm.get_estimation_age_mesh()).
      This is used to link beta-binomial stochs into a larger model,
      for example.

    Results
    -------
    vars : dict
      Return a dictionary of all the relevant PyMC objects for the
      beta binomial model.  vars['rate_stoch'] is of particular
      relevance; this is what is used to link the beta-binomial model
      into more complicated models, like the generic disease model.

    Details
    -------
    The beta binomial model parameters are the following:
      * the mean age-specific rate function
      * confidence in this mean
      * the p_i value for each data observation that has a standard
        error (data observations that do not have standard errors
        recorded are fit as observations of the beta r.v., while
        observations with standard errors recorded have a latent
        variable for the beta, and an observed binomial r.v.).
    """
    vars = {}
    est_mesh = dm.get_estimate_age_mesh()
    if np.any(np.diff(est_mesh) != 1):
        raise ValueError, 'ERROR: Gaps in estimation age mesh must all equal 1'

    # set up age-specific rate function, if it does not yet exist
    if not rate_stoch:
        param_mesh = dm.get_param_age_mesh()
        initial_value = dm.get_initial_value(key)

        # find the logit of the initial values, which is a little bit
        # of work because initial values are sampled from the est_mesh,
        # but the logit_initial_values are needed on the param_mesh
        logit_initial_value = mc.logit(
            interpolate(est_mesh, initial_value, param_mesh))
        
        logit_rate = mc.Normal('logit(%s)' % key,
                               mu=-5 * np.ones(len(param_mesh)),
                               tau=1.e-2,
                               value=logit_initial_value)
        vars['logit_rate'] = logit_rate

        @mc.deterministic(name=key)
        def rate_stoch(logit_rate=logit_rate):
            return interpolate(
                param_mesh, mc.invlogit(logit_rate), est_mesh)

    vars['rate_stoch'] = rate_stoch

    #confidence = 1000
    #confidence = mc.Normal('conf_%s' % key, mu=100.0, tau=1./(30.)**2)
    confidence = mc.Gamma('conf_%s' % key, alpha=100., beta=100. / 1000.)
    
    @mc.deterministic(name='alpha_%s' % key)
    def alpha(rate=rate_stoch, confidence=confidence):
        return rate * confidence

    @mc.deterministic(name='beta_%s' % key)
    def beta(rate=rate_stoch, confidence=confidence):
        return (1. - rate) * confidence

    vars['conf'] = confidence
    vars['alpha'] = alpha
    vars['beta'] = beta

    # set up priors and observed data
    prior_str = dm.get_priors(key)
    vars['priors'] = generate_prior_potentials(prior_str, est_mesh, rate_stoch, confidence)

    vars['logit_p_stochs'] = []
    vars['p_stochs'] = []
    vars['beta_potentials'] = []
    vars['observed_rates'] = []
    vars['data'] = data_list
    for d in data_list:
        # set up observed stochs for all relevant data
        id = d['id']
        
        if d['value'] == MISSING:
            print 'WARNING: data %d missing value' % id
            continue

        # ensure all rate data is valid
        d_val = dm.value_per_1(d)
        d_se = dm.se_per_1(d)
        
        if d_val < 0 or d_val > 1:
            print 'WARNING: data %d not in range [0,1]' % id
            continue

        if d['age_start'] < est_mesh[0] or d['age_end'] > est_mesh[-1]:
            raise ValueError, 'Data %d is outside of estimation range---([%d, %d] is not inside [%d, %d])' \
                % (d['id'], d['age_start'], d['age_end'], est_mesh[0], est_mesh[-1])

        age_indices = indices_for_range(est_mesh, d['age_start'], d['age_end'])
        age_weights = d['age_weights']
        # if the data has a standard error, model it as a realization
        # of a beta binomial r.v.
        if d_se > 0:
            logit_p = mc.Normal('logit(p_%d)' % id, 0., 1/(10.)**2,
                                value=mc.logit(d_val + NEARLY_ZERO))
            p = mc.InvLogit('p_%d' % id, logit_p)

            @mc.potential(name='beta_potential_%d' % id)
            def potential_p(p=p,
                            alpha=alpha, beta=beta,
                            age_indices=age_indices,
                            age_weights=age_weights):
                a = rate_for_range(alpha, age_indices, age_weights)
                b = rate_for_range(beta, age_indices, age_weights)
                return mc.beta_like(trim(p, NEARLY_ZERO, 1. - NEARLY_ZERO), a, b)

            denominator = max(100., d_val * (1 - d_val) / d_se**2.)
            numerator = d_val * denominator
            obs = mc.Binomial('data_%d' % id, value=numerator, n=denominator, p=p, observed=True)

            vars['logit_p_stochs'].append(logit_p)
            vars['p_stochs'].append(p)
            vars['beta_potentials'].append(potential_p)
        else:
            # if the data is a point estimate with no uncertainty
            # recorded, model it as a realization of a beta r.v.
            @mc.observed
            @mc.stochastic(name='data_%d' % id)
            def obs(value=d_val,
                    alpha=alpha, beta=beta,
                    age_indices=age_indices,
                    age_weights=age_weights):
                a = rate_for_range(alpha, age_indices, age_weights)
                b = rate_for_range(beta, age_indices, age_weights)
                return mc.beta_like(trim(value, NEARLY_ZERO, 1. - NEARLY_ZERO), a, b)
            
        vars['observed_rates'].append(obs)
        
    return vars
