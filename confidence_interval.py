
# %%
n = 500 # 8 hr
p = .419 # long term win rate
q = .497 # long term loss rate
B = 1.19 # long term average win amount
L = 1.01 # long term average loss amount

mu = B*p - L*q
variance = B*B*p + L*L*q - mu**2
sigma = variance ** 0.5

# Sn = sum(xi)
muS = n*mu
varS = n*variance
sigmaS = sigma*n ** 0.5

# Sn​≈N(n(Bp−Lq),n[B2p+L2q−(Bp−Lq)2])
# 95% CI
ci_lower = muS - 1.96 * sigmaS
ci_upper = muS + 1.96 * sigmaS

print(f"95% CI for Sn: [{ci_lower}, {ci_upper}]")
print(f"Number of trials: {n}")
print(f"Mean of Sn: {muS}")
print(f"Standard deviation of Sn: {sigmaS}")
# print(f"Variance of Sn: {varS}")