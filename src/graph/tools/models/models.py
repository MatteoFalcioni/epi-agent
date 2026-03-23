#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 3 14:30:19 2026

@author: Giulio Colombini
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.integrate import solve_ivp
from scipy.optimize import minimize

### EPIDEMIOLOGICAL MODELS ###

# Susceptible - Infectious - Removed and incidence function.

def sir(t, y, beta, mu, N):
    return np.array([- beta * y[0] * y[1] / N, 
                       beta * y[0] * y[1] / N - mu * y[1],
                       mu * y[1]])

def sir_incidence(x, t_span, N):
    beta, mu, I0, f = x # Respectively beta = infectivity, 
                        #              mu = recovery rate, 
                        #              I0 = initial infective people,
                        #              f = detection fraction.

    y0 = np.array([N-I0, I0, 0.])

    sol = solve_ivp(sir, t_span = (t_span), y0 = y0,
                    args = (beta, mu, N), 
                    t_eval = np.arange(*t_span, 1.),
                    method = 'Radau')
    s, i, r = sol.y

    incidence = f * beta * s * i / N

    return incidence

# Susceptible - Exposed - Infectious - Removed and incidence function.

def seir(t, y, beta, gamma, mu, N):
    return np.array([- beta * y[0] * y[2] / N, 
                       beta * y[0] * y[2] / N - gamma * y[1],
                       gamma* y[1] - mu * y[2],
                       mu * y[2]])

def seir_incidence(x, t_span, N):
    beta, gamma, mu, E0, I0, f = x # Respectively beta  = infectivity, 
                                   #              gamma = symptoms development rate, 
                                   #              mu    = recovery rate, 
                                   #              E0    = initial exposed people,
                                   #              I0    = initial infective people,
                                   #              f     = detection fraction.

    y0 = np.array([N-E0-I0, E0, I0, 0.])

    sol = solve_ivp(seir, t_span = (t_span), y0 = y0,
                    args = (beta, gamma, mu, N), 
                    t_eval = np.arange(*t_span, 1.),
                    method = 'Radau')
    s, e, i, r = sol.y

    incidence = f * gamma * e

    return incidence

### METRICS ###

# Root Mean Square Error

def rmse(x, t_span, model, args, data):
    # x = model parameters which we want to fit.
    # t_span = fitting interval
    # model = callable model(t_span, x, args) providing a prediction.
    # data = fit data to use to compute the metric.

    assert len(data) == t_span[1] - t_span[0],'Shape mismatch between data and t_span.'

    cur_pred_incidence = model(x, t_span, *args)

    gap = cur_pred_incidence - data

    return np.sqrt((gap*gap).sum()/len(gap))

### FITTING FUNCTION ###

def fit(model, objf, data, initial_guess, fixed_args, verbose = True):
    optimum = minimize(objf, x0 = initial_guess,
                             args = ((0., len(data)), model, 
                                     fixed_args, data),
                             bounds=((0., np.inf) for i in range(len(initial_guess))))
    if verbose:
        print(optimum)
    return optimum

### TEST MAIN ###

if __name__ == '__main__':

    N = 886891  # total population (example)
    
    df = pd.read_csv('daily_positives_flu.csv', index_col = 0, parse_dates = True)
    
    beg     = '2025-11-01'
    end_fit = '2025-12-16'
    end_tst = '2026-02-28'
    
    df['0'].plot(color = 'C1')
    df['0'].rolling(7, min_periods = 1, center = False).mean().plot(color = 'C0')
    
    plt.vlines([beg, end_fit, end_tst], ymin = 0., ymax = 50, linestyle = 'dashed',
               color = 'red')
    
    plt.show()
    
    df_fit = df[(df.index >= beg) & (df.index <= end_fit)]
    fit_index = df_fit.index
    df_tst = df[(df.index >= beg) & (df.index <= end_tst)]
    tst_index = df_tst.index
    
    fit_incidence = df_fit['0'].rolling(7, min_periods = 1, 
                                        center = False).mean().to_numpy()
    tst_incidence = df_tst['0'].rolling(7, min_periods = 1, 
                                        center = False).mean().to_numpy()

    initial_guess_sir  = np.array([1., 0.2,      fit_incidence[0]/0.1, 0.1])
    initial_guess_seir = np.array([1., 0.2, 0.2, 
                                       fit_incidence[0]/0.1, fit_incidence[0]/0.1, 
                                       0.1])
    
    optimum_sir  = fit(sir_incidence, rmse, fit_incidence, 
                initial_guess = initial_guess_sir, fixed_args = (N,), verbose = True)

    optimum_seir = fit(seir_incidence, rmse, fit_incidence, 
                initial_guess = initial_guess_seir, fixed_args = (N,), verbose = True)
    
    obeta_sir,               omu_sir,            oI0_sir,  of_sir  = optimum_sir.x 
    obeta_seir, ogamma_seir, omu_seir, oE0_seir, oI0_seir, of_seir = optimum_seir.x 
    
    print("R0_SIR =",  obeta_sir /omu_sir)
    print("R0_SEIR =", obeta_seir/omu_seir)
    
    t_span = (0, len(tst_incidence))
    
    sir_sol_opt = solve_ivp(sir, t_span = t_span, 
                            y0 = np.array([N - oI0_sir, oI0_sir, 0.]),
                            args = (obeta_sir, omu_sir, N), 
                            t_eval = np.arange(*t_span, 1.),
                            method = 'Radau')
    
    s, i, r = sir_sol_opt.y

    pred_incidence_sir = of_sir * obeta_sir * s * i / N
    
    seir_sol_opt = solve_ivp(seir, t_span = t_span, 
                            y0 = np.array([N - oE0_seir - oI0_seir, 
                                           oE0_seir, oI0_seir, 0.]),
                            args = (obeta_seir, ogamma_seir, omu_seir, N), 
                            t_eval = np.arange(*t_span, 1.),
                            method = 'Radau')

    s, e, i, r = seir_sol_opt.y

    pred_incidence_seir = of_seir * ogamma_seir * e
    
    fig, ax = plt.subplots()
    
    ax.plot(tst_index, tst_incidence) 
    ax.plot(tst_index, pred_incidence_sir) 
    ax.plot(tst_index, pred_incidence_seir) 
    ax.vlines([end_fit], ymin = 0., ymax = 50, linestyle = 'dashed',
               color = 'C1')
    
    plt.show()
