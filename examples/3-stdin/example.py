# from os import exit


def main():
    res = input("Enter some number: ")
    try:
        num = int(res)
    except ValueError:
        print("Error: invalid number", res)
        exit(1)

    print(f"\nNumber doubled: {num*2}")


if __name__ == "__main__":
    main()
