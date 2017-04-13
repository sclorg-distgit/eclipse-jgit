%{?scl:%scl_package eclipse-jgit}
%{!?scl:%global pkg_name %{name}}
%{?java_common_find_provides_and_requires}

%global baserelease 2

%global version_suffix 201612231935-r

Name:           %{?scl_prefix}eclipse-jgit
Version:        4.6.0
Release:        2.%{baserelease}%{?dist}
Summary:        Eclipse JGit

License:        BSD
URL:            http://www.eclipse.org/egit/
Source0:        http://git.eclipse.org/c/jgit/jgit.git/snapshot/jgit-%{version}.%{version_suffix}.tar.xz
Patch0:         fix_jgit_sh.patch
# Patch for latest versions of args4j
Patch1:         eclipse-jgit-413163.patch
# Have to patch for latest vesions of jetty
Patch2:         eclipse-jgit-jetty-9.4.0.patch
# Change how feature deps are specified, to avoid embedding versions
Patch3:         jgit-feature-deps.patch

BuildArch: noarch

BuildRequires:  %{?scl_prefix}eclipse-filesystem
BuildRequires:  %{?scl_prefix_maven}maven-local
BuildRequires:  %{?scl_prefix_maven}maven-antrun-plugin
BuildRequires:  %{?scl_prefix_maven}maven-plugin-build-helper
BuildRequires:  %{?scl_prefix_maven}maven-shade-plugin
BuildRequires:  %{?scl_prefix}tycho
BuildRequires:  %{?scl_prefix}args4j
BuildRequires:  %{?scl_prefix_java_common}apache-commons-compress
BuildRequires:  %{?scl_prefix_java_common}xz-java >= 1.1-2
BuildRequires:  %{?scl_prefix}javaewah
BuildRequires:  %{?scl_prefix_java_common}slf4j
BuildRequires:  %{?scl_prefix}jgit
BuildRequires:  %{?scl_prefix_java_common}google-gson
Requires:       %{?scl_prefix}eclipse-filesystem
Requires:       %{?scl_prefix}jgit = %{version}-%{release}

%description
A pure Java implementation of the Git version control system.

%package -n     %{?scl_prefix}jgit-javadoc
Summary:        API documentation for %{pkg_name}

%description -n %{?scl_prefix}jgit-javadoc
%{summary}.

%package -n     %{?scl_prefix}jgit
Summary:        Java-based command line Git interface

%description -n %{?scl_prefix}jgit
Command line Git tool built entirely in Java.

%prep
%{?scl:scl enable %{scl_maven} %{scl} - << "EOF"}
set -e -x
%setup -n jgit-%{version}.%{version_suffix} -q

%patch0
%patch1 -p1
%if 0%{?fedora} >= 25
%patch2 -b .sav
%endif
%patch3

# old jetty
sed -i -e '/Override/d' \
 org.eclipse.jgit.junit.http/src/org/eclipse/jgit/junit/http/RecordingLogger.java

# Disable multithreaded build
rm .mvn/maven.config

# Javaewah change
sed -i -e "s/javaewah/com.googlecode.javaewah.JavaEWAH/g" org.eclipse.jgit.packaging/org.eclipse.jgit{,.pgm}.feature/feature.xml
sed -i -e 's/1.1.6,2.0.0/0.8.0,1.0.0/g' org.eclipse.jgit/META-INF/MANIFEST.MF org.eclipse.jgit.test/META-INF/MANIFEST.MF
sed -i -e 's/WORD_IN_BITS/wordinbits/' org.eclipse.jgit/src/org/eclipse/jgit/internal/storage/file/BitmapIndexImpl.java

# Don't try to get deps from local *maven* repo, use tycho resolved ones
%pom_remove_dep com.googlecode.javaewah:JavaEWAH
for p in $(find org.eclipse.jgit.packaging -name pom.xml) ; do
  grep -q dependencies $p && %pom_xpath_remove "pom:dependencies" $p
done

# Disable "errorprone" compiler
%pom_xpath_remove "pom:build/pom:pluginManagement/pom:plugins/pom:plugin[pom:artifactId='maven-compiler-plugin']/pom:executions" pom.xml
%pom_xpath_remove "pom:build/pom:pluginManagement/pom:plugins/pom:plugin[pom:artifactId='maven-compiler-plugin']/pom:dependencies" pom.xml

# Don't need target platform or repository modules with xmvn
%pom_disable_module org.eclipse.jgit.target org.eclipse.jgit.packaging
%pom_disable_module org.eclipse.jgit.repository org.eclipse.jgit.packaging
%pom_xpath_remove "pom:build/pom:pluginManagement/pom:plugins/pom:plugin/pom:configuration/pom:target" org.eclipse.jgit.packaging/pom.xml

# Don't build source features
%pom_disable_module org.eclipse.jgit.source.feature org.eclipse.jgit.packaging
%pom_disable_module org.eclipse.jgit.pgm.source.feature org.eclipse.jgit.packaging

# Use Equinox OSGi instead of Felix
%pom_change_dep -r org.osgi:org.osgi.core org.eclipse.osgi:org.eclipse.osgi

# Remove unnecessary jacoco and javadoc usage
%pom_remove_plugin org.jacoco:jacoco-maven-plugin
%pom_remove_plugin :maven-javadoc-plugin

# Relax version restriction for args4j
sed -i /org.kohsuke.args4j/s/2\\.1\\.0/3/ $(find -name MANIFEST.MF)

# Don't attach shell script artifact
%pom_remove_plugin org.codehaus.mojo:build-helper-maven-plugin org.eclipse.jgit.pgm

# Does not build due to missing OSGi metadata in httpcomponents-client-cache
sed -i -e '/client\.cache/d' org.eclipse.jgit.http.apache/META-INF/MANIFEST.MF

# Remove org.apache.log4j
%pom_remove_dep log4j:log4j . org.eclipse.jgit.pgm

# org.slf4j.api -> slf4j.api
# org.slf4j.impl.log4j12 -> slf4j.simple
sed -i 's/org\.slf4j\.api/slf4j\.api/
        s/org\.slf4j\.impl\.log4j12/slf4j\.simple/' \
org.eclipse.jgit.packaging/org.eclipse.jgit.feature/feature.xml
%pom_change_dep org.slf4j:slf4j-log4j12 org.slf4j:slf4j-simple . org.eclipse.jgit.pgm

pushd org.eclipse.jgit.packaging
%mvn_package "::pom::" __noinstall
popd
%{?scl:EOF}


%build
%{?scl:scl enable %{scl_maven} %{scl} - << "EOF"}
set -e -x
# Due to a current limitation of Tycho it is not possible to mix pom-first and
# manifest-first builds in the same reactor build hence two separate invocations

# First invocation installs jgit so the second invocation will succeed
%mvn_build -f --post install:install \
  -- -Dmaven.repo.local=$(pwd)/org.eclipse.jgit.packaging/.m2

# Second invocation builds the eclipse features
pushd org.eclipse.jgit.packaging
%mvn_build -j -f -- -Dfedora.p2.repos=$(pwd)/.m2
popd
%{?scl:EOF}


%install
%{?scl:scl enable %{scl_maven} %{scl} - << "EOF"}
set -e -x
# The macro does not allow us to change the "namespace" value, but here we want to
# set it to something other than the SRPM name, so explode the macro
xmvn-install -R .xmvn-reactor -n jgit -d %{buildroot}
install -dm755 %{buildroot}%{_javadocdir}/jgit
cp -pr .xmvn/apidocs/* %{buildroot}%{_javadocdir}/jgit
echo '%{_javadocdir}/jgit' >>.mfiles-javadoc

pushd org.eclipse.jgit.packaging
%mvn_install
popd

# Binary
install -dm 755 %{buildroot}%{_bindir}
install -m 755 org.eclipse.jgit.pgm/jgit.sh %{buildroot}%{_bindir}/jgit
%{?scl:EOF}


%files -f org.eclipse.jgit.packaging/.mfiles
%doc LICENSE README.md

%files -n %{?scl_prefix}jgit -f .mfiles
%{_bindir}/jgit
%dir %{_javadir}/jgit
%dir %{_mavenpomdir}/jgit
%doc LICENSE README.md

%files -n %{?scl_prefix}jgit-javadoc -f .mfiles-javadoc
%doc LICENSE README.md

%changelog
* Mon Jan 16 2017 Mat Booth <mat.booth@redhat.com> - 4.6.0-2.2
- Accomodate for old jetty version

* Mon Jan 16 2017 Mat Booth <mat.booth@redhat.com> - 4.6.0-2.1
- Auto SCL-ise package for rh-eclipse46 collection

* Thu Jan 05 2017 Mat Booth <mat.booth@redhat.com> - 4.6.0-2
- Bump to rebuild symlinks

* Wed Jan 04 2017 Mat Booth <mat.booth@redhat.com> - 4.6.0-1
- Update to latest release

* Tue Oct 4 2016 Alexander Kurtakov <akurtako@redhat.com> 4.5.0-2
- Remove no longer needed patch.

* Tue Oct 4 2016 Alexander Kurtakov <akurtako@redhat.com> 4.5.0-1
- Update to upstream 4.5.0 release.

* Wed Aug 03 2016 Sopot Cela <scela@redhat.com> - 4.4.1-1
- Upgrade to 4.4.1

* Fri Jul 01 2016 Mat Booth <mat.booth@redhat.com> - 4.4.0-4
- Fix IllegalStateException when starting git daemon from the command line

* Wed Jun 15 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.4.0-3
- Add missing build-requires

* Mon Jun 13 2016 Mat Booth <mat.booth@redhat.com> - 4.4.0-2
- Rebuild to regenerate symlinks

* Mon Jun 13 2016 Mat Booth <mat.booth@redhat.com> - 4.4.0-1
- Update to latest release

* Mon May 02 2016 Mat Booth <mat.booth@redhat.com> - 4.3.0-2
- Avoid embedding versions of external deps in features. This avoids the need to
  rebuild when a dependency changes version.

* Fri Apr 15 2016 Sopot Cela <scela@redhat.com> - 4.3.0-1
- Upgrade to 4.3.0

* Wed Apr  6 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.2.0-9
- Rebuild for slf4j 1.7.21

* Wed Mar 30 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.2.0-8
- Rebuild for slf4j 1.7.20

* Thu Mar 24 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.2.0-7
- Rebuild for slf4j 1.7.19

* Mon Feb 29 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.2.0-6
- Rebuild for slf4j 1.7.18

* Mon Feb 22 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.2.0-5
- Rebuild for slf4j 1.7.17

* Wed Feb 17 2016 Alexander Kurtakov <akurtako@redhat.com> 4.2.0-4
- Rebuild for latest slf4j.

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 4.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Mon Jan 25 2016 Mat Booth <mat.booth@redhat.com> - 4.2.0-2
- Rebuilt to generate symlinks

* Fri Jan 22 2016 Mat Booth <mat.booth@redhat.com> - 4.2.0-1
- Update to latest upstream release
- Add patch for latest version of jetty

* Tue Dec 08 2015 Mat Booth <mat.booth@redhat.com> - 4.1.1-2
- Rebuild to re-generate symlinks

* Tue Dec 08 2015 Mat Booth <mat.booth@redhat.com> - 4.1.1-1
- Update to latest upstream release

* Sun Nov 29 2015 Mat Booth <mat.booth@redhat.com> - 4.1.0-6
- Fix a problem with command line "jgit daemon" invocation
- This should also fix rhbz#1228138

* Mon Nov 16 2015 Alexander Kurtakov <akurtako@redhat.com> 4.1.0-5
- Rebuild for latest slf4j.

* Mon Oct 12 2015 Mat Booth <mat.booth@redhat.com> - 4.1.0-4
- Drop R on slf4j.

* Thu Oct 08 2015 Roland Grunberg <rgrunber@redhat.com> - 4.1.0-3
- Use slf4j.simple instead of slf4j.log4j12.

* Wed Sep 30 2015 Mat Booth <mat.booth@redhat.com> - 4.1.0-2
- Regenerate symlinks

* Tue Sep 29 2015 Mat Booth <mat.booth@redhat.com> - 4.1.0-1
- Update to 4.1.0

* Mon Sep 14 2015 Roland Grunberg <rgrunber@redhat.com> - 4.0.1-5
- Rebuild as an Eclipse p2 Droplet.

* Tue Jul  7 2015 Mikolaj Izdebski <mizdebsk@redhat.com> - 4.0.1-4
- Relax version restriction for args4j

* Tue Jun 30 2015 Mat Booth <mat.booth@redhat.com> - 4.0.1-3
- Does not require eclipse-platform, only eclipse-filesystem
- Drop incomplete SCL macros

* Wed Jun 24 2015 Alexander Kurtakov <akurtako@redhat.com> 4.0.1-2
- Rebuild to fix symlinks.

* Wed Jun 24 2015 Alexander Kurtakov <akurtako@redhat.com> 4.0.1-1
- Update to 4.0.1.

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 4.0.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Wed Jun 10 2015 Alexander Kurtakov <akurtako@redhat.com> 4.0.0-2
- Rebuild to fix symlinks.

* Tue Jun 9 2015 Alexander Kurtakov <akurtako@redhat.com> 4.0.0-1
- Update to 4.0 final.

* Mon Jun 1 2015 Alexander Kurtakov <akurtako@redhat.com> 4.0.0-0.2.rc2
- Switch to xz tarball.

* Wed May 27 2015 Alexander Kurtakov <akurtako@redhat.com> 4.0.0-0.1.rc2
- Update to 4.0 rc2.

* Thu May 14 2015 Alexander Kurtakov <akurtako@redhat.com> 3.7.1-1
- Update to 3.7.1 release.

* Mon Mar 02 2015 Roland Grunberg <rgrunber@redhat.com> - 3.7.0-2
- Manually add slf4j-log4j12 requires.

* Mon Mar 02 2015 Roland Grunberg <rgrunber@redhat.com> - 3.7.0-1
- Update to upstream 3.7.0.

* Fri Jan 23 2015 Roland Grunberg <rgrunber@redhat.com> - 3.6.2-2
- Use Equinox's OSGi runtime instead of Felix's.

* Fri Jan 23 2015 Alexander Kurtakov <akurtako@redhat.com> 3.6.2-1
- Update to upstream 3.6.2.

* Mon Jan 5 2015 Alexander Kurtakov <akurtako@redhat.com> 3.6.1-1
- Update to upstream 3.6.1.

* Fri Dec 19 2014 Alexander Kurtakov <akurtako@redhat.com> 3.5.3-1
- Update to upstream 3.5.3 release.

* Thu Dec 18 2014 Alexander Kurtakov <akurtako@redhat.com> 3.5.2-1
- Update to upstream 3.5.2 release.

* Tue Nov 11 2014 Mat Booth <mat.booth@redhat.com> - 3.5.0-3
- Rebuild to generate correct symlinks
- Drop unnecessary requires (now autogenerated by xmvn)

* Fri Nov 07 2014 Mat Booth <mat.booth@redhat.com> - 3.5.0-2
- Build/install eclipse plugin with mvn_build/mvn_install

* Fri Oct 03 2014 Mat Booth <mat.booth@redhat.com> - 3.5.0-1
- Update to latest upstream release 3.5.0

* Thu Jun 26 2014 Mat Booth <mat.booth@redhat.com> - 3.4.1-1
- Update to latest upstream release 3.4.1
- Drop unnecessary BRs

* Fri Jun 13 2014 Alexander Kurtakov <akurtako@redhat.com> 3.4.0-1
- Update to upstream 3.4.0.

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 3.3.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri May 30 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 3.3.2-5
- Use .mfiles geterated during build

* Fri May 30 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.2-4
- Add missing Rs ( rhbz #1079706 ).

* Wed May 28 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.2-3
- Rebuild for latest commons-compress.

* Wed May 21 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.2-2
- Fix compile against latest args4j.

* Fri Apr 25 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.2-1
- Update to 3.3.2.

* Mon Mar 31 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.1-2
- Remove bundled commons-compress.

* Fri Mar 28 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.1-1
- Update to 3.3.1.

* Tue Mar 11 2014 Alexander Kurtakov <akurtako@redhat.com> 3.3.0-1
- Update to 3.3.0.

* Sun Dec 29 2013 Alexander Kurtakov <akurtako@redhat.com> 3.2.0-1
- Update to 3.2.0.

* Thu Oct 3 2013 Krzysztof Daniel <kdaniel@redhat.com> 3.1.0-1
- Update to Kepler SR1.

* Mon Aug 5 2013 Krzysztof Daniel <kdaniel@redhat.com> 3.0.0-7
- Add missing jgit plugin back.

* Tue Jul 16 2013 Krzysztof Daniel <kdaniel@redhat.com> 3.0.0-6
- Change the build system to mvn-rpmbuild.
- Use feclipse-maven-plugin to install things.
- Bug 413163 - Incompatible change in latest args4j: multiValued removed from @Option

* Fri Jul 5 2013 Neil Brian Guzman <nguzman@redhat.com> 3.0.0-5
- Bump release

* Tue Jun 25 2013 Neil Brian Guzman <nguzman@redhat.com> 3.0.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Tue Jun 25 2013 Krzysztof Daniel <kdaniel@redhat.com> 3.0.0-3
- Add missing R: javaewah to eclipse-jgit.

* Tue Jun 25 2013 Krzysztof Daniel <kdaniel@redhat.com> 3.0.0-2
- Move symlinks to eclipse-jgit.
- Fix jgit classpath.

* Thu Jun 20 2013 Neil Brian Guzman <nguzman@redhat.com> 3.0.0-1
- Update to 3.0.0 release

* Tue May 14 2013 Krzysztof Daniel <kdaniel@redhat.com> 2.3.1-2
- Rebuild with latest icu4j.

* Thu Feb 21 2013 Roland Grunberg <rgrunber@redhat.com> - 2.3.1-1
- SCL-ize package.

* Thu Feb 21 2013 Roland Grunberg <rgrunber@redhat.com> - 2.3.1-1
- Update to 2.3.1 release.

* Thu Feb 14 2013 Roland Grunberg <rgrunber@redhat.com> - 2.2.0-3
- jgit subpackage should own its symlinked dependencies.

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.2.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Jan 3 2013 Krzysztof Daniel <kdaniel@redhat.com> 2.2.0-1
- Update to 2.2.0 release.

* Mon Oct 1 2012 Alexander Kurtakov <akurtako@redhat.com> 2.1.0-1
- Update to 2.1.0 release.

* Wed Jul 18 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Mon Jul 2 2012 Alexander Kurtakov <akurtako@redhat.com> 2.0.0-1
- Update to 2.0.0 upstream release.

* Fri Apr 27 2012 Severin Gehwolf <sgehwolf@redhat.com> 1.3.0-3
- Use eclipse-pdebuild over old pdebuild script.

* Thu Apr 26 2012 Severin Gehwolf <sgehwolf@redhat.com> 1.3.0-2
- Tweak .spec so as to avoid modifying to much of the .spec file
- Fix upstream 1.3 release sources.

* Fri Feb 17 2012 Andrew Robinson <arobinso@redhat.com> 1.3.0-1
- Update to 1.3.0 upstream release.

* Thu Jan 5 2012 Alexander Kurtakov <akurtako@redhat.com> 1.2.0-2
- Build eclipse plugin first to not interfere with maven artifacts.

* Thu Jan 5 2012 Alexander Kurtakov <akurtako@redhat.com> 1.2.0-1
- Update to 1.2.0 release.

* Fri Oct 28 2011 Andrew Robinson <arobinso@redhat.com> 1.1.0-4
- Add jsch jar to the classpath.

* Fri Oct 28 2011 Alexander Kurtakov <akurtako@redhat.com> 1.1.0-3
- Drop libs subpackage and use the sh script directly instead of the shaded executable.
- Install jars in _javadir subdir as per guidelines.

* Thu Oct 27 2011 Andrew Robinson <arobinso@redhat.com> 1.1.0-2
- Added Java libraries, javadocs and console binary subpackages.

* Fri Sep 23 2011 Andrew Robinson <arobinso@redhat.com> 1.1.0-1
- Update to upstream release 1.1.0.

* Tue Jun 14 2011 Chris Aniszczyk <zx@redhat.com> 1.0.0-2
- Update to upstream release 1.0.0.201106090707-r.

* Tue Jun 07 2011 Chris Aniszczyk <zx@redhat.com> 1.0.0-1
- Update to upstream release 1.0.0.

* Tue May 03 2011 Chris Aniszczyk <zx@redhat.com> 0.12.1-1
- Update to upstream release 0.12.1.

* Tue Feb 22 2011 Chris Aniszczyk <zx@redhat.com> 0.11.3-1
- Update to upstream release 0.11.3.

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.10.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Wed Dec 22 2010 Chris Aniszczyk <zx@redhat.com> 0.10.1-1
- Update to upstream release 0.10.1.

* Thu Oct 7 2010 Chris Aniszczyk <zx@redhat.com> 0.9.3-1
- Update to upstream release 0.9.3.

* Wed Sep 15 2010 Severin Gehwolf <sgehwolf@redhat.com> 0.9.1-1
- Update to upstream release 0.9.1.

* Thu Aug 26 2010 Severin Gehwolf <sgehwolf at, redhat.com> 0.9.0-0.1.20100825git
- Make release tag more readable (separate "0.1" and pre-release tag by ".").

* Wed Aug 25 2010 Severin Gehwolf <sgehwolf at, redhat.com> 0.9.0-0.120100825git
- Pre-release version of JGit 0.9.0

* Fri Jun 25 2010 Severin Gehwolf <sgehwolf at, redhat.com> 0.8.4-2
- Increase release number to make tagging work.

* Wed Jun 23 2010 Severin Gehwolf <sgehwolf at, redhat.com> 0.8.4-1
- Rebase to 0.8.4 release.

* Mon Apr 12 2010 Jeff Johnston <jjohnstn@redhat.com> 0.7.1-1
- Rebase to 0.7.1 release.

* Tue Feb 9 2010 Alexander Kurtakov <akurtako@redhat.com> 0.6.0-0.1.git20100208
- New git snapshot.

* Thu Nov 5 2009 Alexander Kurtakov <akurtako@redhat.com> 0.6.0-0.1.git20091029
- Correct release.

* Thu Oct 29 2009 Alexander Kurtakov <akurtako@redhat.com> 0.6.0-0.git20091029.1
- Initial package
