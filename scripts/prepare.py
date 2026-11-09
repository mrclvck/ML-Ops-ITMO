import csv

with open("data/raw.csv") as f:
    reader = csv.DictReader(f)
    total = sum(int(row["value"]) for row in reader)

with open("data/result.csv", "w") as f:
    f.write("total\n")
    f.write(f"{total}\n")

print(f"Total: {total}")