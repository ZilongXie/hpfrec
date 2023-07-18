try:
    import setuptools
    from setuptools import setup
    from setuptools import Extension
except ImportError:
    from distutils.core import setup
    from distutils.extension import Extension
from Cython.Distutils import build_ext
import numpy
import sys, os, subprocess, warnings, re
import platform

found_omp = True
def set_omp_false():
    global found_omp
    found_omp = False

## Modify this to make the output of the compilation tests more verbose
silent_tests = not (("verbose" in sys.argv)
                    or ("-verbose" in sys.argv)
                    or ("--verbose" in sys.argv))

## Workaround for python<=3.9 on windows
try:
    EXIT_SUCCESS = os.EX_OK
except AttributeError:
    EXIT_SUCCESS = 0

IS_WINDOWS = platform.system() == "Windows"

## https://stackoverflow.com/questions/724664/python-distutils-how-to-get-a-compiler-that-is-going-to-be-used
class build_ext_subclass( build_ext ):
    def build_extensions(self):
        if self.compiler.compiler_type == 'msvc':
            for e in self.extensions:
                e.extra_compile_args += ['/openmp', '/O2', '/GL', '/fp:fast']
        else:
            if not self.check_for_variable_dont_set_march() and not self.check_cflags_contain_arch():
                self.add_march_native()
            self.add_openmp_linkage()
            self.add_no_math_errno()
            self.add_no_trapping_math()
            self.add_O2()
            self.add_std_c99()
            self.add_link_time_optimization()

            # for e in self.extensions:
                # e.extra_compile_args = ['-fopenmp', '-O2', '-march=native', '-std=c99']
                # e.extra_link_args = ['-fopenmp']
                ### Comment: -Ofast gives worse speed than -O2 or -O3
                # e.extra_compile_args += ['-O2', '-std=c99']

        build_ext.build_extensions(self)

    def check_cflags_contain_arch(self):
        if "CFLAGS" in os.environ:
            arch_list = [
                "-march", "-mcpu", "-mtune", "-msse", "-msse2", "-msse3",
                "-mssse3", "-msse4", "-msse4a", "-msse4.1", "-msse4.2",
                "-mavx", "-mavx2", "-mavx512"
            ]
            for flag in arch_list:
                if flag in os.environ["CFLAGS"]:
                    return True
        return False

    def check_for_variable_dont_set_march(self):
        return "DONT_SET_MARCH" in os.environ

    def add_march_native(self):
        args_march_native = ["-march=native", "-mcpu=native"]
        for arg_march_native in args_march_native:
            if self.test_supports_compile_arg(arg_march_native):
                for e in self.extensions:
                    e.extra_compile_args.append(arg_march_native)
                break

    def add_link_time_optimization(self):
        args_lto = ["-flto=auto", "-flto"]
        for arg_lto in args_lto:
            if self.test_supports_compile_arg(arg_lto):
                for e in self.extensions:
                    e.extra_compile_args.append(arg_lto)
                    e.extra_link_args.append(arg_lto)
                break

    def add_no_math_errno(self):
        arg_fnme = "-fno-math-errno"
        if self.test_supports_compile_arg(arg_fnme):
            for e in self.extensions:
                e.extra_compile_args.append(arg_fnme)
                e.extra_link_args.append(arg_fnme)

    def add_no_trapping_math(self):
        arg_fntm = "-fno-trapping-math"
        if self.test_supports_compile_arg(arg_fntm):
            for e in self.extensions:
                e.extra_compile_args.append(arg_fntm)
                e.extra_link_args.append(arg_fntm)

    def add_O2(self):
        arg_O2 = "-O2"
        if self.test_supports_compile_arg(arg_O2):
            for e in self.extensions:
                e.extra_compile_args.append(arg_O2)
                e.extra_link_args.append(arg_O2)

    def add_std_c99(self):
        arg_std_c99 = "-std=c99"
        if self.test_supports_compile_arg(arg_std_c99):
            for e in self.extensions:
                e.extra_compile_args.append(arg_std_c99)
                e.extra_link_args.append(arg_std_c99)

    def add_openmp_linkage(self):
        arg_omp1 = "-fopenmp"
        arg_omp2 = "-fopenmp=libomp"
        args_omp3 = ["-fopenmp=libomp", "-lomp"]
        arg_omp4 = "-qopenmp"
        arg_omp5 = "-xopenmp"
        is_apple = sys.platform[:3].lower() == "dar"
        args_apple_omp = ["-Xclang", "-fopenmp", "-lomp"]
        args_apple_omp2 = ["-Xclang", "-fopenmp", "-L/usr/local/lib", "-lomp", "-I/usr/local/include"]
        has_brew_omp = False
        if is_apple:
            try:
                res_brew_pref = subprocess.run(["brew", "--prefix", "libomp"], capture_output=True)
                if res_brew_pref.returncode == EXIT_SUCCESS:
                    brew_omp_prefix = res_brew_pref.stdout.decode().strip()
                    args_apple_omp3 = ["-Xclang", "-fopenmp", f"-L{brew_omp_prefix}/lib", "-lomp", f"-I{brew_omp_prefix}/include"]
                    has_brew_omp = True
            except Exception as e:
                pass


        if self.test_supports_compile_arg(arg_omp1, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args.append(arg_omp1)
                e.extra_link_args.append(arg_omp1)
        elif is_apple and self.test_supports_compile_arg(args_apple_omp, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args += ["-Xclang", "-fopenmp"]
                e.extra_link_args += ["-lomp"]
        elif is_apple and self.test_supports_compile_arg(args_apple_omp2, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args += ["-Xclang", "-fopenmp"]
                e.extra_link_args += ["-L/usr/local/lib", "-lomp"]
                e.include_dirs += ["/usr/local/include"]
        elif is_apple and has_brew_omp and self.test_supports_compile_arg(args_apple_omp3, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args += ["-Xclang", "-fopenmp"]
                e.extra_link_args += [f"-L{brew_omp_prefix}/lib", "-lomp"]
                e.include_dirs += [f"{brew_omp_prefix}/include"]
        elif self.test_supports_compile_arg(arg_omp2, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args += ["-fopenmp=libomp"]
                e.extra_link_args += ["-fopenmp"]
        elif self.test_supports_compile_arg(args_omp3, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args += ["-fopenmp=libomp"]
                e.extra_link_args += ["-fopenmp", "-lomp"]
        elif self.test_supports_compile_arg(arg_omp4, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args.append(arg_omp4)
                e.extra_link_args.append(arg_omp4)
        elif self.test_supports_compile_arg(arg_omp5, with_omp=True):
            for e in self.extensions:
                e.extra_compile_args.append(arg_omp5)
                e.extra_link_args.append(arg_omp5)
        else:
            set_omp_false()
            for e in self.extensions:
                e.sources = [re.sub(r"^(.*)return1\.pyx$", r"\1return0.pyx", s) for s in e.sources]

    def test_supports_compile_arg(self, comm, with_omp=False):
        is_supported = False
        try:
            if not hasattr(self.compiler, "compiler"):
                return False
            if not isinstance(comm, list):
                comm = [comm]
            print("--- Checking compiler support for option '%s'" % " ".join(comm))
            fname = "hpfrec_compiler_testing.c"
            with open(fname, "w") as ftest:
                ftest.write(u"int main(int argc, char**argv) {return 0;}\n")
            try:
                if not isinstance(self.compiler.compiler, list):
                    cmd = list(self.compiler.compiler)
                else:
                    cmd = self.compiler.compiler
            except Exception:
                cmd = self.compiler.compiler
            if with_omp:
                with open(fname, "w") as ftest:
                    ftest.write(u"#include <omp.h>\nint main(int argc, char**argv) {return 0;}\n")
            try:
                val = subprocess.run(cmd + comm + [fname], capture_output=silent_tests).returncode
                is_supported = (val == EXIT_SUCCESS)
            except Exception:
                is_supported = False
        except Exception:
            pass
        try:
            os.remove(fname)
        except Exception:
            pass
        return is_supported


setup(
    name = 'hpfrec',
    packages = ['hpfrec'],
    version = '0.2.9',
    description = 'Hierarchical Poisson matrix factorization for recommender systems',
    author = 'David Cortes',
    url = 'https://github.com/david-cortes/hpfrec',
    keywords = ['poisson', 'probabilistic', 'factorization', 'variational inference', 'collaborative filtering'],
    classifiers = [],

    cmdclass = {'build_ext': build_ext_subclass},
    ext_modules = [ Extension(
                        "hpfrec.cython_loops_float",
                        sources=[
                            "hpfrec/cython_float_nonwindows.pyx"
                            if not IS_WINDOWS
                            else
                            "hpfrec/cython_float_windows.pyx"
                        ],
                        include_dirs=[numpy.get_include()]
                    ),
                    Extension(
                        "hpfrec.cython_loops_double",
                        sources=[
                            "hpfrec/cython_double_nonwindows.pyx"
                            if not IS_WINDOWS
                            else
                            "hpfrec/cython_double_windows.pyx"
                        ],
                        include_dirs=[numpy.get_include()]
                    ),
                    Extension(
                        "hpfrec._check_openmp",
                        sources=["hpfrec/return1.pyx" if found_omp else "hpfrec/return0.pyx"],
                        include_dirs=[numpy.get_include()]
                    ) ]
)

if not found_omp:
    omp_msg  = "\n\n\nCould not detect OpenMP. Package will be built without multi-threading capabilities. "
    omp_msg += " To enable multi-threading, first install OpenMP"
    if (sys.platform[:3] == "dar"):
        omp_msg += " - for macOS: 'brew install libomp'\n"
    else:
        omp_msg += " modules for your compiler. "
    
    omp_msg += "Then reinstall this package from scratch: 'pip install --upgrade --no-deps --force-reinstall hpfrec'.\n"
    warnings.warn(omp_msg)
