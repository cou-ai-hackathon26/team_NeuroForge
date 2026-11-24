# Testing and evaluation
Run `pytest -q`. Tests cover seven demo emergency triggers, medium/incomplete status, keyword extraction and emergency precedence.

## Synthetic evaluation plan
Run at least these Bangla utterances through the full pipeline:
1. গর্ভাবস্থায় রক্তপাত হচ্ছে।
2. আমার খিঁচুনি হয়েছে।
3. প্রচণ্ড মাথাব্যথা, চোখে ঝাপসা দেখি।
4. আজ বাচ্চা আগের মতো নড়ছে না।
5. পেটে খুব তীব্র ব্যথা।
6. খুব শ্বাসকষ্ট হচ্ছে।
7. জ্বর এবং খুব দুর্বল লাগছে।
8. জ্বর, পেটব্যথা ও মাথাব্যথা একসাথে।
9. আমি ২৮ সপ্তাহের গর্ভবতী, অন্য তথ্য নেই।
10. ট্রান্সক্রিপশন অস্পষ্ট: 'মাথা ... চোখ ...'
Record symptom-level precision/recall, missed emergency signs, hallucinated symptoms, JSON validity and latency. No model benchmark or clinical validation is claimed by this starter. Use recorded consenting synthetic voice actors or generated non-identifiable speech only; document dialect/noise limitations.
