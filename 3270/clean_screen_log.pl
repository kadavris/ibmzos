#!/bin/perl
use warnings;
use strict;
use Getopt::Long;
# made by Andrej Pakhutin
# use to clean [wx]3270 "Save screen to file" output 
# cygwin environment implied

$#ARGV == -1 and help();

my @in_files = ( );

my $horizontal = 0; # use -z if snap is from IMS log

GetOptions(
  'a' => \&grab_all,
  'z' => \$horizontal,
);

my %macros;

init();

if ( $#in_files == -1 )
{
  $#ARGV == -1 and help();
  process( @ARGV );
}

for my $infile ( @in_files )
{
  print "\n+ Processing $infile\n";
  process( $infile );
}

############################################################
sub grab_all
{
  die 'You cant use -a with other arguments' if defined( $ARGV[1] );

  my $dir = '/cygdrive/' . $ENV{'USERPROFILE'} . '/Desktop';
  $dir =~ s/\\/\//g;
  $dir =~ s/://;

  print "Scanning $dir for grabs...\n";

  open L, "/usr/bin/find $dir -name x3scr.\\*.txt -print |" or die "find: $dir";
  
  for (<L>)
  {
    s/\s+$//;

    s?^.+[/\\]??;

    push @in_files, $dir . '/' . $_;
    print "Found log: $_\n";
  }

  close L;
}

############################################################
sub process
{
  my $infile = $_[0];

  open IN, '<', $infile or die "$infile: $!";

  my $outfile;

  if ( $#_ == 0 ) # just in file name: getting browsed module name
  {
    while(<IN>)
    {
      pre_clean();

      if ( /^[\s.]+BROWSE\s+(\S+)\s+Line\s+((\d+\s+Col\s+\d+\s+\d+)|(.+))/ )
      {
        $outfile = lc("$1");

        -f $outfile and die "out file $outfile already exists!";

        print "Output name: $outfile\n";

        if ( defined($4) ) # message within status position
        {
          print '*' x 40, "\n", "* Message: $4\n", '*' x 40, "\n";
        }

        last;
      } # if /BROWSE/
    } # while(IN)

    if ( $outfile eq '' )
    {
      $outfile = $infile . '.cleaned.txt';
      $outfile =~ s/.*[\/\\]//g;
      seek IN, 0, 0; # reset it
    }
  }
  else
  {
    $outfile = $_[1];
  }

  # if this file is core, so we don't do macro subst
  my $core = ($outfile =~ /^(dv|\w+\.[^.]+\.dv)/i) ? 1 : 0;

  open OUT, '>', $outfile or die "out file $outfile: $!";

  # skipping till the end of top header
  while(<IN>)
  {
    last if /\*{10,}\s*Top of Data/i;
    last if /^\s*Command\s===>.+?Scroll\s===>/;
  }

  my $header = 0;
  my $line = 0; # for horizontal buffering
  my @out_buf; # screen buffer for the case of horizontal gluing

  if ( $horizontal ) # IMS log, etc
  {
    while(<IN>)
    {
      s/[\r\n]+//g;
      #if ( /^\s+BROWSE\s+\S+\s+Line\s+\d+Col\s+\d+\s+\d+/ ) # new screen
      if ( /^\s*Command\s===>.+?Scroll\s===>/ )
      {
        $line = 0;
        next;
      }

      $out_buf[ $line++ ] .= $_;
    }

    for ( @out_buf )
    {
      print OUT $_, "\n";
    }
  }
  else
  {
    while(<IN>)
    {
      s/\s+$//;

      if ( /^(\s*\.){10,}\s*$/ || /^={50,}/ )
      {
         ++$header;
         print STDERR ' =';
         next;
      }

      pre_clean();
     
      last if /\*{10,}\s*Bottom of Data \*+/;

      if ( $header > 0 )
      {
         ++$header;

         if ( /^\s*Command\s+===>/i )
         {
           $header = 0;
           next;
         }
         else
         {
           print STDERR $header;
           next;
         }
      }

      # pre-process C code
      s/\?\?\(/[/g;
      s/\?\?\)/]/g;

      if ( ! $core )
      {
        for my $k ( keys %macros )
        {
          if ( $k eq lc('%pl%') )
          {
            s/$k/$macros{$k}/g;
          }
          else
          {
            s/$k/$k>$macros{$k}/g;
          }
        }
      }

      # runbooks continuation:
      s/%[\r\n]+//m;

      print OUT "$_\n";
    }

  } # if ! horiz

  close OUT;
  close IN;

  my $arcf = "${outfile}.grab.txt";

  if ( $infile ne $arcf )
  {
    mkdir 'grabs';
    system qq~/bin/mv "$infile" "./grabs/$arcf"~;
  }
}

#######################################
sub pre_clean
{
  s/^\s+\. //;
  s/\s*\.\s*$//;
}

#######################################
sub init
{
  $macros{'%PL%'}   = 'VG';
  $macros{'%FL%'}   = 'G';
  $macros{'%DL%'}   = 'TABLE';
  $macros{'%B0%'}   = '         TWERK AND BOUNCE SINISTRIFICATION/BEEN OUT         ';
  $macros{'%B1%'}   = 'TBSBO';
  $macros{'%B2%'}   = 'T B S B O';
  $macros{'%B3%'}   = 'TWERK AND BOUNCE SINISTRIFICATION/BEEN OUT';
  $macros{'%B3L%'}  = 'Twerk And Bounce Sinistrification/Been Out';
  $macros{'%B5%'}   = '  T B S B O  ';
  $macros{'%B6%'}   = '  T B S B O  ';
  $macros{'%B7%'}   = 'TBSBO';
  $macros{'%TM%'}   = ' ';
  $macros{'%NL%'}   = 'Company ';
  $macros{'%NS%'}   = 'Company '; 
  $macros{'%N9%'}   = 'Company ';
  $macros{'%NLL%'}  = 'Company .';
  $macros{'%NSL%'}  = 'Company ';
  $macros{'%N9L%'}  = 'Company ';
  $macros{'%NL1%'}  = 'Company '; 
  $macros{'%NL2%'}  = '';
  $macros{'%NL3%'}  = '';
  $macros{'%NL1L%'} = 'Company ';
  $macros{'%NL2L%'} = '';
  $macros{'%NL3L%'} = '';
}

#######################################
sub help
{
  print "Use: clean_screen_log.pl [options] [capture_file [clean_file_FULLNAME]]\n";
  print "Where either capture file name or -a switch present\n";
  print "\t-a automatically looks for standard named files on your win desktop\n\tand put the converted results into current folder\n";
  print "\t-z used for gluing wide, horizontal stuff like IMS logs\n";
  print "You may supply cleaned file name for yur convenience as a secondary arg\n";
  exit;
}