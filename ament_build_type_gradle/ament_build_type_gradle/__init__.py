# Copyright 2014 Open Source Robotics Foundation, Inc.
# Copyright 2016 Esteve Fernandez <esteve@apache.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Implements the BuildType support for gradle based ament packages."""

import os
import shutil

from ament_tools.helper import extract_argument_group

from ament_package.templates import configure_file
from ament_package.templates import get_environment_hook_template_path
from ament_package.templates import get_package_level_template_names

from ament_tools.build_types.common import expand_package_level_setup_files
from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType
from ament_tools.helper import deploy_file

import pkg_resources

IS_WINDOWS = os.name == 'nt'

def get_gradle_executable():
    gradle_script = 'gradle.bat' if IS_WINDOWS else 'gradle'
    if 'GRADLE_HOME' in os.environ:
        gradle_home = os.environ['GRADLE_HOME']
        gradle_path = os.path.join(gradle_home, 'bin', gradle_script)
        if os.path.isfile(gradle_path):
            return gradle_path
    return shutil.which(gradle_script)


GRADLE_EXECUTABLE = get_gradle_executable()


class AmentGradleBuildType(BuildType):
    build_type = 'ament_gradle'
    description = "ament package built with Gradle"

    def prepare_arguments(self, parser):
        parser.add_argument(
            '--ament-gradle-args',
            nargs='*',
            default=[],
            help="Arbitrary arguments which are passed to 'ament_gradle' Gradle projects. "
                 "Argument collection can be terminated with '--'.")

    def argument_preprocessor(self, args):
        # The ament CMake pass-through flag collects dashed options.
        # This requires special handling or argparse will complain about
        # unrecognized options.
        args, gradle_args = extract_argument_group(args, '--ament-gradle-args')
        extras = {
            'ament_gradle_args': gradle_args,
        }
        return args, extras

    def extend_context(self, options):
        ce = super(AmentGradleBuildType, self).extend_context(options)
        ce.add('ament_gradle_args', options.ament_gradle_args)
        return ce

    def on_build(self, context):
        cmd_args = [
            '-Pament.build_space=' + context.build_space,
            '-Pament.install_space=' + context.install_space,
            '-Pament.dependencies=' + ':'.join(context.build_dependencies),
            '-Pament.build_tests=' + str(context.build_tests),
        ]
        cmd_args += context.ament_gradle_args

        cmd = [GRADLE_EXECUTABLE]
        cmd += cmd_args
        cmd += ['assemble']

        yield BuildAction(cmd, cwd=context.source_space)

        environment_hooks_path = os.path.join(
            'share', context.package_manifest.name, 'environment')

        ext = '.sh' if not IS_WINDOWS else '.bat'
        path_environment_hook = os.path.join(
            environment_hooks_path, 'path' + ext)

        # expand environment hook for JAVAPATH
        ext = '.sh.in' if not IS_WINDOWS else '.bat.in'
        template_path = self.get_environment_hook_template_path('javapath' + ext)
        javapath = os.path.join('$AMENT_CURRENT_PREFIX', 'share', context.package_manifest.name, 'java', '*') + ':' \
            + os.path.join('$AMENT_CURRENT_PREFIX', 'lib', 'java', '*')
        content = configure_file(template_path, {
            'JAVAPATH': javapath
        })
        javapath_environment_hook = os.path.join(
            environment_hooks_path, os.path.basename(template_path)[:-3])
        destination_path = os.path.join(
            context.build_space, javapath_environment_hook)
        destination_dir = os.path.dirname(destination_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        with open(destination_path, 'w') as h:
            h.write(content)

        environment_hooks = [
            path_environment_hook,
            javapath_environment_hook,
        ]

        # expand package-level setup files
        expand_package_level_setup_files(context, environment_hooks, environment_hooks_path)

    def on_test(self, context):
        cmd_args = [
            '-Pament.build_space=' + context.build_space,
            '-Pament.install_space=' + context.install_space,
            '-Pament.dependencies=' + ':'.join(context.build_dependencies),
            '-Pament.build_tests=' + str(context.build_tests),
        ]
        cmd_args += context.ament_gradle_args

        cmd = [GRADLE_EXECUTABLE]
        cmd += cmd_args
        cmd += ['test']

        yield BuildAction(cmd, cwd=context.source_space)

    def on_install(self, context):
        # deploy PATH environment hook
        ext = '.sh' if not IS_WINDOWS else '.bat'
        template_path = get_environment_hook_template_path('path' + ext)
        deploy_file(
            context, os.path.dirname(template_path), os.path.basename(template_path),
            dst_subfolder=os.path.join('share', context.package_manifest.name, 'environment'))

        # deploy JAVAPATH environment hook
        destination_file = 'javapath' + ('.sh' if not IS_WINDOWS else '.bat')
        deploy_file(
            context, context.build_space,
            os.path.join(
                'share', context.package_manifest.name, 'environment',
                destination_file))

        # create marker file
        marker_file = os.path.join(
            context.install_space,
            'share', 'ament_index', 'resource_index', 'packages',
            context.package_manifest.name)
        if not os.path.exists(marker_file):
            marker_dir = os.path.dirname(marker_file)
            if not os.path.exists(marker_dir):
                os.makedirs(marker_dir)
            with open(marker_file, 'w'):  # "touching" the file
                pass

        for name in get_package_level_template_names():
            assert name.endswith('.in')
            deploy_file(
                context, context.build_space,
                os.path.join(
                    'share', context.package_manifest.name, name[:-3]))

        cmd_args = [
            '-Pament.build_space=' + context.build_space,
            '-Pament.install_space=' + context.install_space,
            '-Pament.dependencies=' + ':'.join(context.build_dependencies),
            '-Pament.build_tests=' + str(context.build_tests),
        ]

        cmd_args += context.ament_gradle_args

        cmd = [GRADLE_EXECUTABLE]
        cmd += cmd_args
        cmd += ['assemble']

        yield BuildAction(cmd, cwd=context.source_space)
        
        #Deploy libs dependencies
        filesDir = os.path.join(context.build_space, 'lib', 'java')
        if os.path.exists(filesDir):
            for filename in os.listdir(filesDir):
                deploy_file(
                context, context.build_space,
                os.path.join(
                    'lib', 'java',
                    os.path.basename(filename)))
                
        #Deploy share files
        self.deploy_files(context, os.path.join('share', context.package_manifest.name, 'java'))
                
        #Deploy scripts
        filesDir = os.path.join(context.build_space, 'bin')
        if os.path.exists(filesDir):
            for filename in os.listdir(filesDir):
                deploy_file(
                context, context.build_space,
                os.path.join(
                    'bin',
                    os.path.basename(filename)))

    def on_uninstall(self, context):
        cmd_args = [
            '-Pament.build_space=' + context.build_space,
            '-Pament.install_space=' + context.install_space,
            '-Pament.dependencies=' + ':'.join(context.build_dependencies),
            '-Pament.build_tests=' + str(context.build_tests),
        ]

        cmd_args += context.ament_gradle_args

        cmd = [GRADLE_EXECUTABLE]
        cmd += cmd_args
        cmd += ['clean']

        yield BuildAction(cmd, cwd=context.source_space)
        
    def deploy_files(self, context, filesDir):
        dir = os.path.join(context.build_space, filesDir)
        
        if os.path.exists(dir):
            for filename in os.listdir(dir):
                if not os.path.isdir(os.path.join(dir, os.path.basename(filename))):
                    deploy_file(
                        context,
                        context.build_space,
                        os.path.join(filesDir, os.path.basename(filename)))
                else:
                    self.deploy_files(context, os.path.join(filesDir, os.path.basename(filename)))

    def get_environment_hook_template_path(self, name):
	    return pkg_resources.resource_filename('ament_build_type_gradle', 'template/environment_hook/' + name)
