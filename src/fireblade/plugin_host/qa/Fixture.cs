using System.ComponentModel;
using System.Globalization;
public sealed class FixtureReader {
 public BindingList<FixtureRow> DataList {get;}=[];
 public string FileDescription=>"Fireblade QA reader";
 public HashSet<string> ExpectedHeaders {get;}=["Text,Identifier"];
 public void ProcessFile(string path)=>DataList.Add(new FixtureRow {Text=File.ReadAllText(path),Identifier="0001"});
}
public sealed class FixtureRow {public string Text{get;set;}="";public string Identifier{get;set;}="";public bool Flag{get;set;}=true;public DateTime Time{get;set;}=new DateTime(2026,1,1,0,0,0,DateTimeKind.Utc).AddTicks(1);public ulong LargeId{get;set;}=9007199254740993;public FixtureDetails Details {get;set;}=new FixtureDetails();}
public sealed class FixtureDouble {
 public string Name=>"FixtureDouble";
 public object Evaluate(params object[] values)=>decimal.Parse(values[0].ToString()!,CultureInfo.InvariantCulture)*2;
 public Type ResultType(params Type[] values)=>typeof(decimal);
}
public sealed class FixtureEcho {
 public string Name=>"FixtureEcho";
 public object? Evaluate(params object[] values)=>values[0];
 public Type ResultType(params Type[] values)=>typeof(string);
}

public sealed class FixtureTypes {
 public string Name=>"FixtureTypes";
 public object Evaluate(params object[] values)=>values[0] is DateTime d && d.Ticks==new DateTime(2026,1,1).Ticks+1 && values[1] is ulong id && id==9007199254740993;
 public Type ResultType(params Type[] values)=>typeof(bool);
}

public sealed class FixturePause {
 public string Name=>"FixturePause";
 public object Evaluate(params object[] values) {Thread.Sleep(10000);return "done";}
 public Type ResultType(params Type[] values)=>typeof(string);
}
public sealed class FixtureDetails {private int secret=37;public int ReadSecret()=>secret;public void SetSecret(int value)=>secret=value;[System.Text.Json.Serialization.JsonIgnore] public FixtureDetails Self=>this;public string Name{get;set;}="évidence";public FixtureDetails? Missing=>null;public List<FixtureAmount> SingleChild=>[Children[0]];public List<FixtureAmount> Children{get;set;}=[new(){Amount=3},new(){Amount=7}];}
public sealed class FixtureAmount {public int Amount{get;set;}}

public sealed class FixtureSameObject {
 public string Name=>"FixtureSameObject";
 public object Evaluate(params object[] values)=>ReferenceEquals(values[0],values[1]) && values[0] is FixtureDetails d && ReferenceEquals(d,d.Self);
 public Type ResultType(params Type[] values)=>typeof(bool);
}
public sealed class FixtureChildren {
 public string Name=>"FixtureChildren";
 public object Evaluate(params object[] values)=>values[0] is List<FixtureAmount> rows && rows.Sum(r=>r.Amount)==10;
 public Type ResultType(params Type[] values)=>typeof(bool);
}
public sealed class FixtureMake {
 public string Name=>"FixtureMake";
 public object Evaluate(params object[] values) {var d=new FixtureDetails();d.SetSecret(73);return d;}
 public Type ResultType(params Type[] values)=>typeof(FixtureDetails);
}
public sealed class FixtureSecret {
 public string Name=>"FixtureSecret";
 public object Evaluate(params object[] values)=>values[0] is FixtureDetails d ? d.ReadSecret() : throw new InvalidOperationException("Original FixtureDetails CLR instance required");
 public Type ResultType(params Type[] values)=>typeof(int);
}
public sealed class FixturePass {
 public string Name=>"FixturePass";
 public object? Evaluate(params object[] values)=>values[0];
 public Type ResultType(params Type[] values)=>typeof(object);
}
public sealed class FixturePauseObject {
 public string Name=>"FixturePauseObject";
 public object Evaluate(params object[] values) {if(values[0] is not FixtureDetails)throw new Exception("CLR instance required");Thread.Sleep(10000);return true;}
 public Type ResultType(params Type[] values)=>typeof(bool);
}

public sealed class FixtureChildAmount {
 public string Name=>"FixtureChildAmount";
 public object Evaluate(params object[] values)=>values[0] is FixtureAmount child ? child.Amount : throw new InvalidOperationException("Original CLR child required");
 public Type ResultType(params Type[] values)=>typeof(int);
}
