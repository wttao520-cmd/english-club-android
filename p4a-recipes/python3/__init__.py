# -*- coding: utf-8 -*-
"""覆盖 p4a 官方 python3 recipe：禁用 Android 不提供的 grp 组函数。

问题现象
--------
第一轮：编译 Modules/grpmodule.c 失败
    error: implicit declaration of function 'setgrent' / 'getgrent' / 'endgrent'

第二轮：编译 Modules/posixmodule.c 失败（initgroups 内部调用 setgroups）
    error: implicit declaration of function 'initgroups'

原因
----
Android 的 bionic 只提供 getgrgid / getgrnam，不提供组数据库遍历与初始化：
setgrent / getgrent / endgrent / initgroups / setgroups 均不存在。
但 CPython 的 configure 在交叉编译时误判这些函数存在，定义了对应的
HAVE_*，编译期即报 implicit declaration（被 -Werror 放大为错误）。

解决
----
沿用 p4a 既有的 ac_cv_* 机制，让 configure 认为这些函数与头文件不存在，
相关代码被 #ifdef 跳过。本应用不涉及用户组管理，禁用无功能损失。
"""

from pythonforandroid.recipes.python3 import Python3Recipe


class Python3RecipeGrpFix(Python3Recipe):
    configure_args = Python3Recipe.configure_args + [
        # ---- 头文件级禁用（决定整个模块是否编译）----
        # grp.h：bionic 只有 getgrgid/getgrnam，无组遍历。禁用后 grp 模块不编译。
        'ac_cv_header_grp_h=no',
        # pwd.h：同族预防。pwdmodule.c 的 getpwall 与 grpmodule.c 同构，
        # 若不整块禁用，下一轮大概率在 pwdmodule.c 报 setpwent/getpwent 错误。
        'ac_cv_header_pwd_h=no',
        # ---- 函数级禁用（posixmodule.c 的 os.initgroups / os.setgroups）----
        # configure 用「链接检测」判定这些函数存在（现代 NDK 统一 sysroot 的
        # libc.so 里有符号），但 minapi=24 时头文件声明被 #if __ANDROID_API__
        # 屏蔽 → HAVE_* 被误判定义 → 编译期 implicit declaration 报错。
        # ac_cv_*=no 让 configure 跳过检测直接判无，相关代码被 #ifdef 跳过。
        'ac_cv_func_initgroups=no',
        'ac_cv_func_setgroups=no',
        'ac_cv_func_setgrent=no',
        'ac_cv_func_getgrent=no',
        'ac_cv_func_endgrent=no',
        'ac_cv_func_setpwent=no',
        'ac_cv_func_getpwent=no',
        'ac_cv_func_endpwent=no',
        # 同族预防：bionic 无此实现（登录名查询），本应用不需要
        'ac_cv_func_getlogin=no',
        'ac_cv_func_getlogin_r=no',
    ]


recipe = Python3RecipeGrpFix()
