## Strategy 1: Baseline: Direct Prediction
**Prompt Framework**: Direct Input->Output pairs. No system prompt.

| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-27 18:21:45 | 1-30 | 0.4667 | 30/30 | 609.60s | [View Log](runs/easy/strategy_1-27-18-11/detail.md) | T2:Pat(15%); T3:Pat(36%); T6:Fail; T10:Pat(12%); T17:Col; T18:Pat(33%); T20:Dim; T21:Pat(7%); T22:Fmt; T23:Col; T24:Fmt; T25:Pat(17%); T26:Fmt; T27:Dim; T29:Pat(18%); T30:Dim |
| 2025-12-27 19:56:16 | 1-30 | 0.2667 | 30/30 | 165.56s | [View Log](runs/easy/strategy_1-27-19-53/detail.md) | T1:Pat(33%); T2:Col; T4:Near; T6:Fail; T7:Near; T8:Near; T10:Pat(16%); T11:Pat(11%); T12:Dim; T13:Near; T17:Col; T18:Pat(17%); T20:Dim; T21:Pat(6%); T22:Col; T23:Pat(22%); T24:Dim; T25:Pat(41%); T26:Pat(46%); T27:Dim; T29:Pat(19%); T30:Dim |
| 2025-12-27 21:40:48 | 1-30 | 0.5000 | 30/30 | 664.65s | [View Log](runs/easy/strategy_1-27-21-29/detail.md) | T2:Near; T6:Fail; T8:Near; T10:Pat(12%); T17:Col; T20:Dim; T21:Pat(7%); T22:Pat(23%); T23:Col; T24:Pat(1%); T25:Pat(22%); T26:Dim; T27:Pat(62%); T28:Pat(1%); T29:Pat(19%) |
| 2026-01-06 22:51:30 | 1-30 | 0.4667 | 30/30 | 289.30s | [View Log](runs/easy/strategy_1-06-22-46/detail.md) | T6:Fail; T8:Near; T10:Pat(12%); T11:Pat(44%); T17:Col; T18:Pat(50%); T20:Pat(67%); T21:Pat(9%); T22:Col; T23:Col; T24:Col; T25:Pat(32%); T27:Col; T28:Col; T29:Pat(18%); T30:Dim |


## Strategy 2: Strategy A: Standard CoT
**Prompt Framework**: Baseline + 'Let's think step by step' suffix.

| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-27 18:35:35 | 1-30 | 0.4333 | 30/30 | 709.51s | [View Log](runs/easy/strategy_2-27-18-23/detail.md) | T2:Pat(15%); T3:Pat(11%); T8:Near; T10:Near; T12:Dim; T17:Col; T18:Col; T20:Dim; T21:Pat(4%); T22:Col; T23:Col; T24:Pat(3%); T25:Pat(13%); T26:Dim; T27:Dim; T29:Pat(18%); T30:Dim |
| 2025-12-27 20:06:37 | 1-30 | 0.5000 | 30/30 | 616.70s | [View Log](runs/easy/strategy_2-27-19-56/detail.md) | T2:Pat(30%); T3:Pat(8%); T6:Fail; T8:Pat(56%); T10:Pat(16%); T17:Col; T20:Dim; T21:Pat(6%); T22:Col; T23:Col; T24:Pat(3%); T25:Pat(24%); T27:Dim; T28:Pat(18%); T29:Pat(23%) |
| 2025-12-27 21:52:53 | 1-30 | 0.5333 | 30/30 | 722.02s | [View Log](runs/easy/strategy_2-27-21-40/detail.md) | T8:Pat(44%); T10:Near; T17:Col; T20:Dim; T21:Pat(9%); T22:Col; T23:Col; T24:Pat(4%); T25:Pat(35%); T26:Dim; T27:Dim; T28:Pat(9%); T29:Pat(26%); T30:Dim |

## Strategy 3: Strategy B: Sparse Rep
**Prompt Framework**: Coordinate format (r,c):v + CoT.

| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-27 19:33:34 | 1-30 | 0.1000 | 30/30 | 617.17s | [View Log](runs/easy/strategy_3-27-19-23/detail.md) | T1:Pat(44%); T3:Dim; T4:Dim; T5:Col; T7:Dim; T8:Dim; T10:Pat(20%); T11:Col; T12:Dim; T13:Col; T14:Pat(24%); T15:Dim; T16:Col; T17:Col; T18:Col; T19:Col; T20:Dim; T21:Col; T22:Dim; T23:Col; T24:Dim; T25:Dim; T26:Dim; T27:Dim; T28:Dim; T29:Dim; T30:Dim |
| 2025-12-27 20:19:29 | 1-30 | 0.2333 | 30/30 | 769.61s | [View Log](runs/easy/strategy_3-27-20-06/detail.md) | T2:Pat(15%); T4:Pat(16%); T7:Dim; T8:Near; T10:Near; T11:Pat(31%); T12:Dim; T13:Col; T14:Near; T16:Pat(22%); T17:Col; T18:Pat(50%); T20:Dim; T21:Pat(7%); T22:Pat(27%); T23:Col; T24:Dim; T25:Col; T26:Pat(41%); T27:Dim; T28:Dim; T29:Dim; T30:Dim |
| 2025-12-27 22:03:05 | 1-30 | 0.3667 | 30/30 | 609.71s | [View Log](runs/easy/strategy_3-27-21-52/detail.md) | T3:Near; T4:Dim; T7:Dim; T8:Pat(56%); T10:Pat(16%); T12:Near; T17:Col; T18:Dim; T20:Dim; T21:Col; T22:Fmt; T23:Col; T24:Dim; T25:Col; T26:Dim; T27:Dim; T28:Dim; T29:Dim; T30:Dim |

## Strategy 4: Strategy C: Python Programmer
**Prompt Framework**: Role: Python Expert. Write transform() function.

| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-27 18:56:50 | 1-30 | 0.2667 | 30/30 | 471.76s | [View Log](runs/easy/strategy_4-27-18-48/detail.md) | T3:Dim; T4:Near; T5:Dim; T6:Fail; T8:Dim; T10:Pat(12%); T11:Pat(11%); T12:Dim; T16:Fmt; T17:Col; T19:Pat(11%); T20:Fmt; T21:Col; T22:Col; T23:Col; T24:Pat(2%); T25:Fmt; T26:Dim; T27:Dim; T28:Pat(10%); T29:Fmt; T30:Dim |
| 2025-12-27 20:29:03 | 1-30 | 0.1000 | 30/30 | 571.44s | [View Log](runs/easy/strategy_4-27-20-19/detail.md) | T1:Pat(17%); T2:Dim; T3:Dim; T4:Near; T5:Dim; T6:Dim; T7:Near; T8:Pat(33%); T10:Pat(16%); T11:Near; T13:Fail; T15:Pat(44%); T16:Fmt; T17:Col; T18:Pat(50%); T19:Dim; T20:Dim; T21:Col; T22:Col; T23:Col; T24:Pat(2%); T25:Pat(33%); T26:Dim; T27:Dim; T28:Pat(10%); T29:Col; T30:Dim |
| 2025-12-27 22:12:21 | 1-30 | 0.2667 | 30/30 | 552.91s | [View Log](runs/easy/strategy_4-27-22-03/detail.md) | T3:Dim; T4:Pat(40%); T5:Dim; T7:Dim; T8:Pat(33%); T10:Pat(16%); T12:Near; T13:Pat(33%); T15:Pat(44%); T17:Col; T18:Dim; T20:Dim; T21:Col; T22:Col; T23:Fmt; T24:Pat(2%); T25:Fmt; T26:Dim; T27:Dim; T28:Pat(10%); T29:Col; T30:Dim |

## Strategy 5: Strategy D: Hypothesis & Verification
**Prompt Framework**: Propose 3 rules -> Verify on train -> Apply to test.

| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-27 19:10:26 | 1-30 | 0.5000 | 30/30 | 813.82s | [View Log](runs/easy/strategy_5-27-18-56/detail.md) | T2:Pat(15%); T6:Fail; T10:Pat(12%); T17:Col; T18:Pat(33%); T20:Dim; T21:Pat(7%); T22:Col; T23:Pat(48%); T24:Pat(4%); T25:Pat(51%); T26:Dim; T27:Dim; T29:Fmt; T30:Near |
| 2025-12-27 20:42:31 | 1-30 | 0.4333 | 30/30 | 805.61s | [View Log](runs/easy/strategy_5-27-20-29/detail.md) | T3:Pat(28%); T6:Col; T7:Pat(56%); T8:Pat(44%); T10:Near; T13:Pat(78%); T20:Dim; T21:Pat(8%); T22:Col; T23:Pat(38%); T24:Pat(2%); T25:Pat(41%); T26:Pat(46%); T27:Dim; T28:Pat(1%); T29:Pat(18%); T30:Dim |
| 2025-12-27 22:23:29 | 1-30 | 0.4333 | 30/30 | 666.15s | [View Log](runs/easy/strategy_5-27-22-12/detail.md) | T3:Col; T7:Near; T8:Pat(44%); T10:Pat(12%); T11:Pat(31%); T17:Col; T18:Pat(17%); T21:Pat(4%); T22:Col; T23:Col; T24:Pat(2%); T25:Pat(57%); T26:Dim; T27:Dim; T28:Pat(27%); T29:Col; T30:Dim |

## Strategy 6: Unknown Strategy 6
**Prompt Framework**: Custom Strategy

| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-01-12 00:02:42 | Specific: [2, 7, 10] | 0.0000 | 3/3 | 762.54s | [View Log](runs/easy/strategy_6-11-23-49/detail.md) | T1:Pat(15%); T2:Pat(78%); T3:Pat(28%) |
| 2026-01-12 02:57:28 | Specific: [2] | 0.0000 | 1/1 | 366.75s | [View Log](runs/easy/strategy_6-12-02-51/detail.md) | T1:Pat(19%) |
| 2026-01-12 03:34:44 | Specific: [2] | 0.0000 | 1/1 | 423.53s | [View Log](#) | T1:Pat(22%) |
| 2026-01-06 23:53:14 | 1-5 | 0.8000 | 5/5 | 382.41s | [View Log](runs/easy/strategy_6-06-23-46/detail.md) | T2:Pat(30%) |
| 2026-01-07 00:20:05 | 1-30 | 0.5667 | 30/30 | 1232.47s | [View Log](runs/easy/strategy_6-06-23-59/detail.md) | T2:Near; T10:Near; T17:Col; T20:Pat(13%); T21:Pat(7%); T22:Pat(32%); T23:Col; T24:Pat(4%); T26:Dim; T27:Dim; T28:Pat(7%); T29:Pat(22%); T30:Dim max_retries = 5|
| 2026-01-07 00:53:23 | 1-30 | 0.6333 | 30/30 | 1768.83s | [View Log](runs/easy/strategy_6-07-00-23/detail.md) | T2:Pat(15%); T7:Near; T10:Pat(12%); T20:Dim; T21:Pat(13%); T22:Pat(7%); T23:Pat(43%); T24:Pat(2%); T28:Pat(6%); T29:Pat(18%); T30:Fmt |
| 2026-01-07 01:52:07 | 1-30 | 0.5667 | 30/30 | 2771.40s | [View Log](runs/easy/strategy_6-07-01-05/detail.md) | T2:Pat(30%); T10:Pat(12%); T17:Col; T20:Dim; T21:Pat(7%); T23:Pat(51%); T24:Pat(2%); T25:Pat(32%); T26:Dim; T27:Dim; T28:Col; T29:Pat(13%); T30:Dim |
| 2026-01-12 09:50:27 | Specific: [2] | 0.0000 | 1/1 | 309.30s | [View Log](runs/strategy_6-12-09-45/detail.md) | T1:Pat(15%) |
| 2026-01-12 10:09:54 | Specific: [2] | 0.0000 | 1/1 | 211.18s | [View Log](runs/strategy_6-12-10-06/detail.md) | T1:Pat(30%) |
| 2026-01-12 10:27:57 | Specific: [2] | 1.0000 | 1/1 | 218.22s | [View Log](runs/strategy_6-12-10-24/detail.md) | All Correct |
| 2026-01-12 11:46:04 | Specific: [2] | 0.0000 | 1/1 | 253.89s | [View Log](runs/strategy_6-12-11-41/detail.md) | T1:Pat(30%) |
| 2026-01-12 16:22:07 | Specific: [2, 7, 10, 20] | 0.0000 | 4/4 | 1037.28s | [View Log](runs/strategy_6-12-16-04/detail.md) | T1:Pat(37%); T2:Pat(78%); T3:Pat(12%); T4:Dim |