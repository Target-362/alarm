# algebra.py
import random
from fractions import Fraction

def generate_equation(difficulty: str = "easy"):
    """
    Генерирует квадратное уравнение ax² + bx + c = 0
    с целыми корнями, чтобы пользователь мог решить его в уме.

    difficulty: easy (корни 1-5), medium (1-10), hard (1-15)
    Возвращает: (a, b, c, roots, text)
    """
    limits = {"easy": 5, "medium": 10, "hard": 15}
    lim = limits.get(difficulty, 5)

    # Выбираем два целых корня
    x1 = random.randint(-lim, lim)
    x2 = random.randint(-lim, lim)

    # a — небольшой коэффициент
    a = random.choice([1, 1, 1, 2, 3])  # чаще 1

    # Восстанавливаем b и c из корней: a(x - x1)(x - x2) = ax² - a(x1+x2)x + a·x1·x2
    b = -a * (x1 + x2)
    c = a * x1 * x2

    # Красиво форматируем для показа
    def term(coef, var, first=False):
        if coef == 0:
            return ""
        sign = ""
        if not first:
            sign = " + " if coef > 0 else " - "
        elif coef < 0:
            sign = "-"
        abs_c = abs(coef)
        if var and abs_c == 1:
            body = var
        else:
            body = f"{abs_c}{var}"
        return sign + body

    text = (term(a, "x²", first=True)
            + term(b, "x")
            + term(c, "")) + " = 0"

    return a, b, c, sorted([x1, x2]), text


def check_answer(user_input: str, roots: list) -> bool:
    """
    Проверяет ответ пользователя. Принимает:
      - "2, -3"
      - "2 -3"
      - "2; -3"
      - "-3, 2" (порядок не важен)
    """
    if not user_input.strip():
        return False
    cleaned = user_input.replace(";", ",").replace(" ", ",")
    parts = [p for p in cleaned.split(",") if p]
    try:
        user_roots = sorted(int(p) for p in parts)
    except ValueError:
        return False
    return user_roots == sorted(roots)


# Быстрый тест при запуске файла напрямую
if __name__ == "__main__":
    for _ in range(5):
        a, b, c, roots, text = generate_equation("easy")
        print(f"{text:30s}  корни: {roots}")