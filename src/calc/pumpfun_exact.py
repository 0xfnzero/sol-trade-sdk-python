"""Rust 5.0.6 checked curve arithmetic, without floating point or native extensions."""
U64=(1<<64)-1
U128=(1<<128)-1
def unsigned(n,maximum,label):
    if type(n) is not int or not 0<=n<=maximum: raise ValueError(f"{label} outside unsigned range")
def buy_exact(virtual_token,virtual_quote,real_token,amount,total_fee_bps=95):
    for n in (virtual_token,virtual_quote,real_token): unsigned(n,U128,"reserve")
    unsigned(amount,U64,"amount");unsigned(total_fee_bps,U64,"fee")
    if amount==0 or virtual_token==0: return 0
    curve_in=max(0,amount*10000//(total_fee_bps+10000)-1)
    if curve_in==0: return 0
    denominator=virtual_quote+curve_in
    if denominator==0 or denominator>U128:return 0
    numerator=curve_in*virtual_token
    return min(0 if numerator>U128 else numerator//denominator,real_token,U64)
def sell_exact(virtual_token,virtual_quote,amount,total_fee_bps=95):
    for n in (virtual_token,virtual_quote): unsigned(n,U128,"reserve")
    unsigned(amount,U64,"amount");unsigned(total_fee_bps,U64,"fee")
    if amount==0 or virtual_token==0:return 0
    numerator=amount*virtual_quote
    if numerator>U128:return U64
    denominator=virtual_token+amount
    if denominator>U128:denominator=1
    gross=numerator//denominator
    fee=(gross*total_fee_bps+9999)//10000
    return min(max(0,gross-fee),U64)
