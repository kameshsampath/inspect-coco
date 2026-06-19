"""Broken Python file with syntax errors for the agent to fix."""


def add(a, b)  # missing colon
    return a + b


def multiply(x, y):
    result = x * y
    return resul  # typo in variable name


def main():
    total = add(20, 22)
    product = multiply(total, 1)
    print(f"Result: {product}"  # missing closing paren


if __name__ == "__main__":
    main()
