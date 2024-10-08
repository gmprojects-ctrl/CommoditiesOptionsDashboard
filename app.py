# Imports
import pandas as pd
import streamlit as st 
import numpy as np
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go   
from scipy.stats import norm
from scipy.stats import normaltest
from statsmodels.tsa.stattools import acf, pacf
import arch

from comm_data import COMMODITY_LIST,get_commodity_data

# Data Path
DATA_PATH = Path("./data.feather")


# Get the log returns
def get_log_returns(dataframe:pd.DataFrame):
    # Shift the return by 1
    previous_returns = dataframe.shift(1)   
    # Convert into numpy arrays
    previous_returns = previous_returns.to_numpy()
    dataframe_ = dataframe.to_numpy()
    
    # Get the returns and flatten it
    log_returns = np.log((dataframe_ / previous_returns))
    
    # Drop the last value
    log_returns = log_returns[1:]
    
    
    # Create a pandas dataframe
    log_returns = pd.DataFrame(log_returns,index=dataframe.index[:-1],columns=['Log Returns'])
    
    return log_returns

# Get the value at risk and expected shortfall
def get_var_cvar(dataframe:pd.DataFrame,rolling_window:int=7,p_value:float=0.05):
    
    # Calculate the log returns
    log_returns = get_log_returns(dataframe)
    
    # Sum the log returns
    sum_log_returns = log_returns.rolling(rolling_window).sum().dropna()
    
    # Calculate the value at risk
    log_value_at_risk = np.quantile(sum_log_returns['Log Returns'],p_value)
    
    # Calculate the expected shortfall
    log_expected_shortfall = sum_log_returns[sum_log_returns['Log Returns'] <= log_value_at_risk].mean().values[0]
    
    return log_value_at_risk,log_expected_shortfall
# Do a Black Sholes Model log_value_at_risk,log_expected_shortfall

def call_black_scholes(S_0:float, K:float, log_vol:float,rate:float, delta_t: float)->float:
    
    # Denominator
    scale = 1/(log_vol * np.sqrt(delta_t))
    
    # dup
    d_up = scale * ( np.log(S_0/K) + delta_t*( rate + 0.5*(log_vol**2)   ))
    
    # d_down
    d_down = d_up - log_vol * np.sqrt(delta_t)
    
    # Discount rate
    discount_rate = np.exp(-rate*(delta_t))
    
    # D_up
    
    d_up_cum = norm().cdf(d_up)
    
    d_down_cum = norm().cdf(d_down)
    
    # Call value
    call_value = S_0 * d_up_cum - K*discount_rate*d_down_cum
    
    # Return
    
    return call_value
    
def put_black_scholes(S_0:float, K:float, log_vol:float,rate:float, delta_t: float)->float:
    
    # Call value
    call_value = call_black_scholes(S_0, K, log_vol,rate, delta_t)
    
    return call_value - S_0 + K*np.exp(-rate*delta_t)
    
    
def MonteCarloVar(mu: float, vol: float, delta_T: float, _periods:int, _simulations:int,p_value:float=0.05):
    
    # Create normal samples
    # That creates mu t + vol * sqrt t N
    normal_samples = np.random.normal(loc=mu*delta_T, scale=vol*np.sqrt(delta_T), size=(_simulations,_periods))
    
    # Sum it up
    normal_samples = np.sum(normal_samples,axis=1)
        
    # Find the p_value
    var_p =  np.quantile(normal_samples,q=p_value)
    
    # Make into a datafram
    sim_returns = pd.DataFrame(normal_samples,columns=['ret'])
    
    # CVAr
    cvar_p = sim_returns.loc[ sim_returns['ret'] <= var_p ].mean().values[0]
    


    return (sim_returns,var_p,cvar_p)
    

# Main function
def main():
    st.title("VAR Models for Commodities")
    
    
    # Create a sidebar to refresh the data
    refresh_data = st.sidebar.button("Refresh Data")
    
    # If the data is refreshed
    if refresh_data:
        try:
            get_commodity_data()
            st.success("Data has been refreshed")
            st.rerun()
        except Exception as e:
            st.error(f"Cannot refresh data : {str(e)}")
    
    
    
    
    # Load the data
    try:
       data = pd.read_feather(DATA_PATH)
       data.index = pd.to_datetime(data.index)
    except Exception as e:
        st.error(f"Cannot load data : {str(e)}")
        raise e 
    
    # Create a data editor
    st.markdown("### Select a Commodity")
    
    commodity = st.selectbox(label="Select a Commodity",options=COMMODITY_LIST.values())
    
    # Enter a period to calculate the value at risk
    period = st.number_input(label="Enter a look back period",min_value=1,step=1,value=365)
    
    # Filter the data
    commodity_data = data[data['Ticker'] == commodity].copy()
    
    # Filter by time
    commodity_data = commodity_data.iloc[-period:,:].copy()
    
    # Sort the data
    commodity_data = commodity_data.sort_index(ascending=True).copy()
    
     # Calculate the log returns
    log_returns = get_log_returns(commodity_data['Close'])
        
    # Get a rolling window
    rolling_window = st.number_input(label="Enter a rolling window",min_value=1,step=1,value=7)
        
    # Sum the log returns
    sum_log_returns = log_returns.rolling(rolling_window).sum().dropna()
    
    
    with st.expander("See data"):
        # Write that data
        st.write(commodity_data)
        
        # Plot the data
        st.plotly_chart(px.line(commodity_data,x=commodity_data.index,y='Close',title=f"{commodity} Prices"))
        

    with st.expander("Historical Var"):
        
        
        

        
        
      
        
        # Calculate the value at risk
        log_value_at_risk = np.quantile(sum_log_returns['Log Returns'],0.05)
        value_at_risk = np.exp(log_value_at_risk)
        
        # Calculate the expected shortfall
        log_expected_shortfall = sum_log_returns[sum_log_returns['Log Returns'] <= log_value_at_risk].mean().values[0]
        expected_shortfall = np.exp(log_expected_shortfall)
        
        
          
        # Plot the data
        st.plotly_chart(px.line(sum_log_returns,x=sum_log_returns.index,y='Log Returns',title=f"{commodity} Log Returns over {rolling_window} day rolling sum"))
        
        # Plot the histogram
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=sum_log_returns['Log Returns'],nbinsx=50))
        fig.add_vline(x=log_value_at_risk,line=dict(color='red'),name="Value at Risk",annotation_text=f"VAR")
        fig.add_vline(x=log_expected_shortfall,line=dict(color='green'),name="Expected Shortfall",annotation_text=f"CVAR")
        
        fig.update_layout(title=f"Histogram of Log Returns for {commodity} over {rolling_window} day period")
        
        st.plotly_chart(fig)
        
        
        # Write the value at risk
        st.write(f"The value at risk is {(1-value_at_risk)*100:.2f}% at the 5% confidence level over a {rolling_window} day period") 
        st.write(f"The expected shortfall is {(1-expected_shortfall)*100:.2f}% at the 5% confidence level over a {rolling_window} day period")

    
    with st.expander("Monte Carlo Var"):
        st.markdown(r"""We will be using the model 
                    $$S_t = S_0 e^{\mu t + \sigma W_t}$$
                    where $S_t$ is the price at time $t$, $S_0$ is the initial price, $\mu$ is the drift, $\sigma$ is the volatility and $W_t$ is the Wiener process.
                    """)
        st.markdown(r"""Thus
                    $$\log(S_t) - \log(S_t-1) = \mu \Delta t + \sigma \sqrt{\Delta t} Z$$
                    where $Z$ is a standard normal random variable.
                    """)
                    
        # Enter a number of simulations
        simulations = st.number_input(label="Enter a number of simulations",min_value=1,step=1,value=100)
        
        # Get the daily vol
        daily_vol = log_returns.std().values[0]
        mu_sample = log_returns.mean().values[0]
        
        # Get the monte carlo var
        sim_returns, MC_var, MC_cvar = MonteCarloVar(mu=mu_sample,vol=daily_vol,delta_T=1,_periods=rolling_window,_simulations=simulations)
        
        # Plot the histogram
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=sim_returns['ret'],nbinsx=50))
        fig.add_vline(x=MC_var,line=dict(color='red'),name="Value at Risk",annotation_text=f"VAR")
        fig.add_vline(x=MC_cvar,line=dict(color='green'),name="Expected Shortfall",annotation_text=f"CVAR")
        fig.update_layout(title=f"Histogram of Monte Carlo Simulations for {commodity} Log Returns over {rolling_window} day period")
        st.plotly_chart(fig)
        
        # Exponeniate MC_var
        st.write(f"The Monte Carlo VAR for {commodity} for a {rolling_window} day period at a 5% significance level is {100- np.exp(MC_var)*100:.2f}%")
        st.write(f"The Monte Carlo expected shortfall for {commodity} for a {rolling_window} day period at a 5% significance level is {100- np.exp(MC_cvar)*100:.2f}%")
    
    with st.expander("Options Pricing"):
        # Using the following formula:
        st.markdown(r"""
                    This is the Black-Scholes formula for a call option:
                    $$C = S_0 N(d_1) - K e^{-rT} N(d_2)$$
                    
                    $C$ is the call price, $S_0$ is the current price of the commodity, $K$ is the strike price, $r$ is the risk free rate, $T$ is the time to expiration and $N$ is the cumulative distribution function of the standard normal distribution.
                """)
        st.markdown(r"""
                    Where:
                    $$d_1 = \frac{1}{\sigma \sqrt{T}} \left( \ln \left( \frac{S_0}{K} \right) + (r + \frac{\sigma^2}{2})T \right)$$
                    and
                    $$d_2 = d_1 - \sigma \sqrt{T}$$
                     
                     
                    """
                    )
        st.markdown(r""" The Put price is given by Put-Call parity:
                    $$P = C - S_0 + K e^{-rT}$$
                    """)
        
        # Calculate the daily volatility
        daily_vol = log_returns.std().values[0]
        
        
        # Calculate volatility
        annual_vol = daily_vol * np.sqrt(252)
        
        # Write the daily volatility of log returns
        st.write(f"The daily volatility of log returns is {daily_vol:.2f}")
        
        # Write the annualized volatility of log returns
        st.write(f"The annualized volatility of log returns is {annual_vol:.2f}")
        
        # Enter a strike price
        strike_price = st.number_input(label="Enter a strike price",min_value=0.0,step=0.01,value=1000.0)
        
        # Enter a risk free rate
        rate = st.number_input(label="Enter a risk free rate",min_value=0.0,step=0.01,value=0.01) / 100
        
        # Enter a time to expiration
        time_to_expiration = st.number_input(label="Enter a time to expiration",min_value=0,step=1,value=1)

        # Divide by 12
        delta_t = time_to_expiration/12
        
        # Calculate the call price
        call_price = call_black_scholes(commodity_data['Close'].iloc[-1],strike_price,annual_vol,rate,delta_t)
        
        # Calculate the put price
        put_price = put_black_scholes(commodity_data['Close'].iloc[-1],strike_price,annual_vol,rate,delta_t)
        
        
        # Write the call price
        st.write(f"The call price is {call_price:.2f}")
        
        # Write the put price
        st.write(f"The put price is {put_price:.2f}")
    with st.expander(f"Using GARCH model to model {commodity} log returns volatility over {rolling_window} day period"):
        st.markdown(r"""     
        Consider the following model:
        $$y_t = \mu + \epsilon_t$$
        
        Where $y_t$ is the log returns, $\mu$ is the mean and $\epsilon_t = \sigma_t * z_t$ where $z_t$ is $N(0,1)£.
        
        Where $y_t$ is the log returns, $\mu$ is the mean, $\sigma_t$ is the volatility and $z_t$ is N(0,1).
        
        Then the GARCH(p,q) model is given by:
        """)
        
        st.markdown(r'$$\sigma_t^2 = \omega + \sum_{i=1}^{p} \alpha_i \epsilon_{t-i}^2 + \sum_{i=1}^{q} \beta_i \sigma_{t-i}^2$$')
        
        st.markdown("""
        We can use a GARCH model to measure the volatility of an assets log returns over a period of time. \n
        In fact we can use the GARCH model to forecast the volatility of an asset over a period of time and its VAR though it is important to note that the GARCH model does not forecast the real returns of an asset,
        nor it is accurate in predicting the future volatility of an asset.""")
        
        # Garch data
        # Scale by 1000
        garch_data = 1000*(sum_log_returns)
        
        
        # Create a 80/20 split
        training_data = garch_data.iloc[:int(len(garch_data)*0.8)].copy()
        testing_data = garch_data.iloc[int(len(garch_data)*0.8):].copy()
        conditional_training_data = training_data.copy()    
       
       
        
        
        
        # Divider
        st.divider()
        
        # Note the log returns are mulitplied by a 1000
        st.markdown("Note the log returns are mulitplied by a 1000")
        st.markdown("Note there is an 80/20 split between the training and testing data")
        
        # Create tabs
        tabs = st.tabs(["Training Data","Testing Data"])
        
        # Show the training data
        with tabs[0]:
            st.write(training_data)
        
        # Show the testing data
        with tabs[1]:
            st.write(testing_data)
            
        # PACF plot 
        pacf_plot = pacf(training_data['Log Returns']**2,nlags=20)
        
        # ACF plot
        acf_plot = acf(training_data['Log Returns']**2,nlags=20)
        
        # Create a figure
        fig = go.Figure()
        # Add the PACF plot
        fig.add_trace(go.Bar(x=np.arange(len(pacf_plot)),y=pacf_plot,name="PACF"))
        
        # Add the ACF plot
        fig.add_trace(go.Bar(x=np.arange(len(acf_plot)),y=acf_plot,name="ACF"))
        
        # Set the xaxis
        fig.update_xaxes(title="Lag Period")
        
        # Set the yaxis
        fig.update_yaxes(title="Correlation")
        
        # Update the layout
        fig.update_layout(title="PACF and ACF plot for GARCH model (note the data is squared as it is sigma^2)")
        
        
        # Plot the figure
        st.plotly_chart(fig)
        
        
        # P,Q input
        p_garch = st.number_input(label="Enter a p value for the GARCH model",min_value=0,step=1,value=1)
        q_garch = st.number_input(label="Enter a q value for the GARCH model",min_value=0,step=1,value=1)

        # Create an Arch Model
        model = arch.arch_model(training_data['Log Returns'],mean='Zero',vol='Garch',p=p_garch,q=q_garch)
        
        # Fit the model
        model_fit = model.fit(disp='off')
        
        # Get the conditional volatility (which is the square root of the variance and equal to the |log returns|)
        conditional_volatility = model_fit.conditional_volatility
        
        # Plot the conditional volatility and log returns of the training data
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=training_data.index,y=conditional_volatility,name="Conditional Volatility", line=dict(color='red')))
        fig.add_trace(go.Scatter(x=training_data.index,y=training_data['Log Returns'],name="Log Returns"))
        fig.update_layout(title=f"Model Fit for GARCH({p_garch,q_garch}) for {commodity} over {rolling_window} day period on Training Data")
        st.plotly_chart(fig)
        
        # Test the model fit
        residuals = training_data['Log Returns'] / conditional_volatility
        residuals.name = 'Residuals'
        
        # Plot the residuals for the training data
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=residuals,nbinsx=50))
        fig.add_vline(x=residuals.mean(),line=dict(color='red'),name="Mean",annotation_text=f"Mean: {residuals.mean():.2f}") 
        fig.add_vline(x=residuals.std(),line=dict(color='green'),name="Standard Deviation",annotation_text=f"Standard Deviation: {residuals.std():.2f}")  
        fig.update_layout(title=f"Histogram of Residuals for GARCH({p_garch,q_garch}) for {commodity} over {rolling_window} day period on Training Data")
        st.plotly_chart(fig)
        
        # Do the norm test
        p_value_training = normaltest(residuals.values)[1]
        
        # Write the p value
        st.write(f"The p value for a normality test for the training residuals is {p_value_training:.2f}")
        
        
        
        
        
        
        
        
        
        # Get the forecast
        forcasted_values = pd.DataFrame(index=testing_data.index,columns=['Forecasted Volatility'])
        
        for i in range(len(testing_data)):
            # Get prediction
            prediction = model_fit.forecast(horizon=1).variance.iloc[0].values[0]
            
            # Forecast
            forcasted_values.iloc[i] = np.sqrt(prediction)
            
            # Update the model
            conditional_training_data = pd.concat([conditional_training_data,testing_data.iloc[i:i+1,:]])
            
            # Update the model
            model = arch.arch_model(conditional_training_data['Log Returns'],mean='Zero',vol='Garch',p=p_garch,q=q_garch)
            
            # Fit the model
            model_fit = model.fit(disp='off')
            
        # Assert conditional training data is the same as garch data
        assert conditional_training_data.equals(garch_data)
        
            
        # Plot the forecasted values
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=testing_data.index,y=forcasted_values['Forecasted Volatility'],name="Forecasted (Conditional) Volatility",line=dict(color='red')))
        fig.add_trace(go.Scatter(x=testing_data.index,y=np.abs(testing_data['Log Returns']),name="ABS Log Returns"))
        fig.update_layout(title=f"Rolling Forecasted (Conditional) Volatility ({p_garch,q_garch}) for {commodity} over {rolling_window} day period on Testing Data")
        st.plotly_chart(fig)
        
        # Get the root mean squared error
        #rmse = np.abs(testing_data['Log Returns']) - forcasted_values['Forecasted Volatility']
        #rmse = np.sqrt(np.mean(rmse**2))
        

        # Write the root mean squared error
        #st.write(f"The root mean squared error is {rmse:.2f}")
        
        # Plot the residuals
        residuals_test = (testing_data['Log Returns'] / forcasted_values['Forecasted Volatility']).astype(float)
        residuals_test.name = 'Residuals'
        
        # Plot the residuals
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=residuals_test,nbinsx=50))
        fig.add_vline(x=residuals_test.mean(),line=dict(color='red'),name="Mean",annotation_text=f"Mean: {residuals_test.mean():.2f}")
        fig.add_vline(x=residuals_test.std(),line=dict(color='green'),name="Standard Deviation",annotation_text=f"Standard Deviation: {residuals_test.std():.2f}")
        fig.update_layout(title=f"Histogram of Residuals for GARCH({p_garch,q_garch}) for {commodity} over {rolling_window} day period on Testing Data")
        st.plotly_chart(fig)
       
        # Do the norm test
        p_value_test = normaltest(residuals_test.values)[1]
        
        # Write the p value
        st.write(f"The p value for a normality test for the testing residuals is {p_value_test:.2f}")
        
        
        # Plot the forecasted VAR (Value at Risk) 
        forecasted_var = forcasted_values['Forecasted Volatility'].astype(float)/ (1000)
        forecasted_var = forecasted_var * norm().ppf(0.05)
        forecasted_var = np.exp(forecasted_var)
        
        # Plot the forecasted VAR
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=testing_data.index,y=forecasted_var,name="Forecasted VAR"))
        fig.update_layout(title=f"Forecasted VAR at 5% signficance level for {commodity} over {rolling_window} day period on Testing Data")
        st.plotly_chart(fig)
        
        # Most reent forecasted VAR
        most_recent_forecasted_var = forecasted_var.iloc[-1]
        
        # Write the most recent forecasted VAR
        st.write(f"The most recent forecasted VAR at the 5% significance level is {(1-most_recent_forecasted_var)*100:.2f}%")
        
        # Write the model summary
        st.write(model_fit.summary())
        
        # Write the model parameters
        st.write(model_fit.params)
        
        

# Run the function
if __name__ == "__main__":
    main()