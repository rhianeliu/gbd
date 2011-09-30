""" Fit a simulation data set"""

import pylab as pl
import pymc as mc
import pandas
import networkx as nx

import data
import data_model
import covariate_model
import consistent_model
import fit_model
reload(fit_model)
import graphics


model = data.ModelData.from_gbd_json('tests/dismoditis.json')

model.parameters['p']['level_value']['age_before'] = 1
model.parameters['i']['level_value']['age_before'] = 25
model.parameters['f']['level_value']['age_before'] = 25
model.parameters['r']['level_value']['age_before'] = 100
for t in 'irfp':
    model.parameters[t]['smoothness']['amount'] = 'Moderately'

knots = pl.arange(30, 86, 5)
ages = pl.arange(knots[0], knots[-1] + 1)
model.parameters['ages'] = ages
for t in 'irfp':
    model.parameters[t]['parameter_age_mesh'] = knots



# create model and priors for top level of hierarchy
prior_models = {}
prior_vars = {}
emp_priors = {}

prior_types = 'i p f'.split()
for t in prior_types:
    print 'fitting', t
    vars = data_model.data_model('prior', model, t,
                                 root_area='all', root_sex='total', root_year='all',
                                 mu_age=None, mu_age_parent=None)

    prior_models[t] = fit_model.fit_data_model(vars)
    prior_vars[t] = vars
    emp_priors[t] = covariate_model.predict_for(model.output_template, model.hierarchy,
                                                'all', 'total', 'all',
                                                'super-region_5', 'male', 2005, vars).mean(axis=0)
    
    graphics.plot_one_type(model, vars, emp_priors, t)
    graphics.plot_one_ppc(vars, t)
    graphics.plot_one_effects(vars, t)
    graphics.plot_convergence_diag(vars)
    pl.figtext(.5, .5, 'AM grouping: %s\niter=%d, burn=%d, thin=%d' % (prior_models[t].am_grouping, prior_models[t].iter, prior_models[t].burn, prior_models[t].thin),
             color='r', va='center', ha='center', fontsize=24)


# create model and priors for (asia_southeast, male, 2005), including estimate of
# super-region_5 to borrow strength
root_area = 'asia_southeast'
subtree = nx.traversal.bfs_tree(model.hierarchy, root_area)
relevant_rows = [i for i, r in model.input_data.T.iteritems() if r['area'] in subtree and r['year_end'] >= 1997 and r['sex'] in ['male', 'total']]
model.input_data = model.input_data.ix[relevant_rows]
vars = consistent_model.consistent_model(model, root_area, 'male', 2005, priors=emp_priors)

# fit model to data
posterior_model = fit_model.fit_consistent_model(vars)

# generate estimates for THA, 2005, male
predict_area = 'THA'
posteriors = {}
for t in 'i r f p rr pf'.split():
    posteriors[t] = covariate_model.predict_for(model.output_template, model.hierarchy,
                                                root_area, 'male', 2005,
                                                predict_area, 'male', 2005, vars[t]).mean(axis=0)

graphics.plot_fit(model, vars, emp_priors, posteriors)
graphics.plot_effects(vars)
for t in 'i f p'.split():
    graphics.plot_one_ppc(vars[t], t)

graphics.plot_convergence_diag(vars)

pl.show()
