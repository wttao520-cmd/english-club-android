# -*- coding: utf-8 -*-
"""覆盖 p4a 官方 python3 recipe：禁用 Android 不提供的 grp 函数。

问题现象
--------
编译 Modules/grpmodule.c 时失败：

    error: implicit declaration of function 'setgrent' is invalid in C99
    error: implicit declaration of function 'getgrent' is invalid in C99
    error: implicit declaration of function 'endgrent' is invalid in C99

原因
----
Android 的 bionic 只提供 getgrgid / getgrnam，不提供遍历 /etc/group 的
setgrent / getgrent / endgrent。但 CPython 的 configure 在交叉编译时误判
这几个函数存在，于是定义了 HAVE_GETGRENT，导致 grpmodule.c 编译失败。

解决
----
p4a 的 python3 recipe 本就用 ac_cv_* 环境变量禁用 Android 不支持的特性
（如 ac_cv_header_bzlib_h=no）。这里沿用同一机制补齐 grp 相关项：
让 configure 认为这些函数不存在，grpmodule.c 中的相关代码被 #ifdef 跳过。

本应用不会用到 grp 模块，禁用它没有任何功能损失。
"""

from pythonforandroid.recipes.python3 import Python3Recipe


class Python3RecipeGrpFix(Python3Recipe):
    configure_args = Python3Recipe.configure_args + [
        'ac_cv_func_setgrent=no',
        'ac_cv_func_getgrent=no',
        'ac_cv_func_endgrent=no',
        'ac_cv_header_grp_h=no',
    ]


recipe = Python3RecipeGrpFix()
