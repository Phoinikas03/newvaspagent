import subprocess
import os

# Na default ENMAX is 102 eV, so 150-400 eV is appropriate
encuts = [150, 200, 250, 300, 350, 400]
results = []

for encut in encuts:
    dir_name = f"encut_{encut}"
    os.makedirs(dir_name, exist_ok=True)
    
    with open("templates/INCAR_static", "r") as f:
        lines = f.readlines()
    
    with open(f"{dir_name}/INCAR", "w") as f:
        for line in lines:
            if "ENCUT =" in line:
                f.write(f"ENCUT = {encut}\n")
            else:
                f.write(line)
    
    os.system(f"cp POSCAR {dir_name}/POSCAR")
    os.system(f"cp KPOINTS {dir_name}/KPOINTS")
    os.system(f"cp POTCAR {dir_name}/POTCAR")
    
    print(f"Running VASP for ENCUT={encut}...")
    # Using mpirun -n 1 vasp_std as requested
    with open(f"{dir_name}/vasp.log", "w") as log_file:
        process = subprocess.run(
            ["mpirun", "-n", "1", "vasp_std"],
            cwd=dir_name,
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
    
    try:
        with open(f"{dir_name}/OSZICAR", "r") as f:
            last_line = f.readlines()[-1]
            energy = float(last_line.split()[4])
            results.append((encut, energy))
            print(f"ENCUT: {encut}, Energy: {energy}")
    except Exception as e:
        print(f"Error reading energy for ENCUT {encut}: {e}")

with open("encut_results.txt", "w") as f:
    f.write("ENCUT(eV)  Energy(eV)\n")
    for encut, energy in results:
        f.write(f"{encut}  {energy}\n")
