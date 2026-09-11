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
        # 只禁用 bionic 真正缺失的函数，不禁头文件。
        #
        # 关键教训：之前禁了 grp.h / pwd.h（ac_cv_header_*=no），结果
        # getgrouplist 这类「Android 上真实存在」的函数因为声明所在头文件
        # 被禁而在 posixmodule.c 中变成 implicit declaration——头文件一禁，
        # 里面所有函数的声明都不可见，而 configure 的链接检测仍会找到符号、
        # 误判 HAVE_GETGROUPLIST 存在。因此：
        #   - 头文件保持启用（声明可见）
        #   - 只禁用 configure 会误判的缺失函数（链接检测被统一 sysroot 骗过）
        #
        # grp 遍历族：bionic 无实现，grpmodule.c 用 #ifdef 引用，禁用后跳过
        'ac_cv_func_setgrent=no',
        'ac_cv_func_getgrent=no',
        'ac_cv_func_endgrent=no',
        # posix 组操作族：bionic 无实现（或 API>=26 才有声明），禁用后 os 模块
        # 不再提供 initgroups/setgroups（本应用不需要）
        'ac_cv_func_initgroups=no',
        'ac_cv_func_setgroups=no',
        # pwd 遍历族：与 grp 同构，预防 pwdmodule.c 报同类错误
        'ac_cv_func_setpwent=no',
        'ac_cv_func_getpwent=no',
        'ac_cv_func_endpwent=no',
        # 登录名查询：bionic 无实现，本应用不需要
        'ac_cv_func_getlogin=no',
        'ac_cv_func_getlogin_r=no',
        # ---- 禁用整个 grp 模块（关键！）----
        # CPython 3.11 的 grpmodule.c 第 281 行对 setgrent() 是「无条件调用」，
        # 没有 #ifdef 保护——ac_cv_func_setgrent=no 只能阻止 pyconfig.h 定义
        # HAVE_SETGRENT，管不住这次裸调用。
        # 模块是否参与编译由 PY_STDLIB_MOD([grp], ..., getgrgid 或 getgrgid_r)
        # 决定，而 bionic 有 getgrgid → 模块被启用 → 编译必炸。
        # 禁掉这两个检测 → MODULE_GRP=missing → grp 模块整体不编译。
        # （标准库对 grp 均为软依赖，本应用不用，无功能损失。）
        'ac_cv_func_getgrgid=no',
        'ac_cv_func_getgrgid_r=no',
    ]


recipe = Python3RecipeGrpFix()
