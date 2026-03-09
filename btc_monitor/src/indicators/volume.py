"""
volume.py – Volume Ratio 計算
"""
import pandas as pd


def calc_volume_ratio(volume: pd.Series, lookback: int = 20) -> float:
    """
    現在足の出来高 / 直近 lookback 本の平均出来高を返す。
    Volume Ratio の定義: 現 15m 足の出来高 ÷ 直近 20 本の平均出来高
    """
    if len(volume) < lookback + 1:
        return 1.0
    current = volume.iloc[-1]
    avg = volume.iloc[-(lookback + 1):-1].mean()
    if avg == 0:
        return 1.0
    return round(current / avg, 2)
