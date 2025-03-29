def main():
    res = input("Enter some number: ")
    try:
        num = int(res)
    except ValueError:
        print("Error: invalid number", res)
        return

    print(f"\nNumber doubled: {num*2}")


if __name__ == "__main__":
    main()
